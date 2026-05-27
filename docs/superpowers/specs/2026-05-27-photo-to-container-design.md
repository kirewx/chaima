# Photo-to-Container — Etikett-Foto füllt Drawer aus

## Problem

Wer ein neu geliefertes Gebinde im Labor in ChAiMa erfasst, tippt heute alles manuell: Chemikalienname, CAS, Lieferant, Menge, Einheit, Reinheit, Lot-Nummer, Kaufdatum. Diese Felder stehen aber alle auf dem Etikett. Das Tippen ist fehleranfällig (CAS-Ziffern verdrehen sich leicht), kostet Zeit, und in der Praxis werden optionale Felder oft weggelassen.

Diese Spec fügt einen Foto-Workflow hinzu: Nutzer fotografiert das Etikett (mobile direkt aus der Kamera), Gemini 2.5 Flash extrahiert die Felder, der bestehende „+ New Chemical"-Drawer wird automatisch vorausgefüllt, PubChem-Anreicherung läuft wie heute, und nach `Create` öffnet sich automatisch der Container-Drawer mit den vorausgefüllten Container-Feldern und dem Foto, das beim Save am Container abgelegt wird.

## Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Vision-Backend | **Gemini 2.5 Flash** via Google AI Studio API (`google-genai` SDK). Free Tier deckt den erwarteten Bedarf (<2 Calls/Tag) vollständig ab. Modell-ID und API-Key über Env-Vars konfigurierbar. |
| 2 | Schema / Output | **Structured Output** (`response_schema`, `response_mime_type="application/json"`) gegen ein Pydantic-Modell `ExtractedLabel`. Kein Free-Text-Parsing. |
| 3 | Datenmodell | **Keine DB-Migration.** `Container.image_path: str \| None` existiert bereits. |
| 4 | Aufgabenteilung Gemini ↔ PubChem | Gemini liefert Etikett-Felder (CAS, Name, Menge, Einheit, Lieferant, Lot, Reinheit, Kaufdatum). PubChem liefert Stammdaten (GHS, Synonyme, SMILES, Molar Mass) wie heute. **Keine Überlappung, keine Duplikation der Verantwortung.** |
| 5 | Capture-Surface | **Mobile Direkt-Kamera** via `<input type="file" accept="image/*" capture="environment">`. Desktop fällt automatisch auf File-Picker zurück. |
| 6 | UI-Pattern | **Kamera-Icon im Drawer-Header** (Option B aus der Brainstorm-Phase), sowohl in `ChemicalForm` als auch in `ContainerForm`. Kein eigener Einstiegspunkt, kein FAB. |
| 7 | Workflow | **Verkettung statt Embedded-Container-Block.** Foto im `ChemicalForm` → Chemical anlegen → Drawer öffnet automatisch `ContainerForm` mit Prefill + Foto. Foto im `ContainerForm` extrahiert nur Container-Felder. |
| 8 | Bild-Upload | **C2 — separater Endpoint `POST /containers/{id}/image`.** Drei Save-Calls (Chemical, Container, Image) statt multipart-vermischtes `POST /containers`. Konsistent mit dem bestehenden Chemical-PDF-Upload-Pattern. |
| 9 | Extract-Endpoint speichert nicht | `POST /chemicals/extract-from-photo` ruft Gemini, verwirft die Bild-Bytes nach dem Call. **Keine Orphan-Bilder.** File lebt im Browser-State bis Save. |
| 10 | Review-Flow | **Felder vorausgefüllt + Highlight.** Erkannte Felder bekommen einen tinted Hintergrund (`accentSoft`) und ein kleines Kamera-Icon. Beim Edit verschwindet das Highlight. |
| 11 | Pre-Resize | Frontend skaliert Bilder vor dem Upload auf max. 2048 px (Canvas, JPEG Quality 0.85). Spart Mobile-Datenvolumen und Gemini-Tokens. |
| 12 | Max-Größe Server | **10 MB hardlimit**, MIME-Whitelist (`image/jpeg`, `image/png`, `image/webp`, `image/heic`), Magic-Byte-Validation via `PIL.Image.verify()`. |
| 13 | Duplicate-Handling | **Keine UI-Erweiterung.** Bestehender `Add container` / `Restore & add container`-Pfad in `ChemicalForm` wird weiterverwendet — er bekommt zusätzlich Prefill + Foto aus dem `DrawerContext` mitgegeben. |
| 14 | Bild-Sicherheit | **Bestehender `/uploads` StaticFiles-Mount bleibt.** UUID-Pfade als einzige Zugriffskontrolle, identisch zur aktuellen Praxis. Auth-gating ist ein separates Refactor für die gesamte Upload-Pipeline. |
| 15 | Cleanup | **Out of scope für v1.** Überschriebene Bilder bleiben auf der Platte. Cleanup-Cron oder sofortiges `unlink` ist Folge-Arbeit. |

## Section 1 — Datenmodell

**Keine Migration.** `Container.image_path: str | None` ist bereits Teil des Modells (`src/chaima/models/container.py:24`). `ContainerRead` exportiert das Feld bereits (`src/chaima/schemas/container.py:117`). Es wird bisher nur nicht gesetzt.

Keine neue Pydantic-Body-Schemas für die zwei neuen Endpoints — beide nehmen `UploadFile = File(...)` ohne weitere Felder.

## Section 2 — Backend

### 2.1 Vision-Service (`src/chaima/services/vision.py` — neu)

```python
class ExtractedLabel(BaseModel):
    cas: str | None = None
    name: str | None = None
    amount: float | None = None
    unit: str | None = None
    supplier_name: str | None = None
    identifier: str | None = None
    purity: str | None = None
    purchased_at: datetime.date | None = None
    confidence: Literal["high", "medium", "low"] = "low"

def extract_from_image(image_bytes: bytes, mime: str) -> ExtractedLabel: ...
```

- Modell: `gemini-2.5-flash`, ID via `CHAIMA_GEMINI_MODEL` (Default `gemini-2.5-flash`).
- API-Key: `CHAIMA_GEMINI_API_KEY`. Wenn leer → `HTTPException(503, "vision_not_configured")`.
- Structured Output: `generate_content(..., config={"response_schema": ExtractedLabel, "response_mime_type": "application/json"})`.
- Prompt (System): kurzer DE/EN-Hinweis „Extrahiere die folgenden Felder vom Chemikalien-Etikett. Lasse Felder leer, wenn nicht eindeutig lesbar. Setze `confidence` auf 'high' nur wenn CAS UND (Name oder Amount+Unit) klar erkennbar sind."
- Timeout 30 s. Bei `genai`-Exception → `HTTPException(502, "vision_service_unavailable")`. Bei Schema-Violation oder leerer Antwort → `ExtractedLabel(confidence="low")` mit allen Feldern `None`.

### 2.2 `POST /chemicals/extract-from-photo` (neu, in `routers/chemicals.py`)

```python
@router.post("/extract-from-photo", response_model=ExtractedLabel)
async def extract_from_photo(
    session: SessionDep,
    member: GroupMemberDep,
    file: UploadFile = File(...),
) -> ExtractedLabel:
    _validate_image(file)            # MIME, Größe ≤10 MB, PIL.verify()
    data = await file.read()
    return vision.extract_from_image(data, file.content_type)
```

- Kein DB-Write. Bytes werden nach dem Call verworfen.
- Auth: jeder Group-Member (analog zu PubChem-Lookup heute).
- `_validate_image`: prüft `file.content_type ∈ {image/jpeg, image/png, image/webp, image/heic}` → 415 sonst; prüft `Content-Length` ≤ 10 MB → 413 sonst; lädt Bytes mit `PIL.Image.open(io.BytesIO(data)).verify()` für Magic-Byte-Validation → 415 bei Fehler.

### 2.3 `POST /containers/{container_id}/image` (neu, in `routers/containers.py`)

```python
@router.post("/{container_id}/image", response_model=ContainerRead)
async def upload_container_image(
    session: SessionDep,
    member: GroupMemberDep,
    container_id: UUID,
    file: UploadFile = File(...),
) -> ContainerRead:
    container = _get_container_or_404(session, container_id, member.group_id)
    _ensure_creator_or_admin(container, member)
    _validate_image(file)
    data = await file.read()
    container.image_path = save_upload(member.group_id, file.filename, data)
    session.commit()
    session.refresh(container)
    return container
```

- Auth: Creator des Containers ODER Group-Admin (gleiche Logik wie Container-Edit).
- Idempotent: ein bestehender `image_path` wird überschrieben; alte Datei bleibt auf der Platte (siehe Decision #15).

### 2.4 Env-Konfiguration

Neu in `.env.example`:

```
# Google AI Studio API key for label OCR. Empty disables the photo-to-container feature.
CHAIMA_GEMINI_API_KEY=
CHAIMA_GEMINI_MODEL=gemini-2.5-flash
```

Neue Abhängigkeit in `pyproject.toml`: `google-genai` (Python-SDK).

## Section 3 — Frontend

### 3.1 `DrawerContext` erweitern

In `frontend/src/components/drawer/DrawerContext.tsx`: `container-new`-Config bekommt zwei optionale Felder:

```ts
type ContainerNewConfig = {
  kind: "container-new";
  chemicalId: string;
  prefill?: {
    identifier?: string;
    amount?: number;
    unit?: string;
    supplier_name?: string;
    purity?: string;
    purchased_at?: string;  // ISO date
  };
  photoFile?: File;
};
```

### 3.2 Neuer Hook `useExtractFromPhoto`

`frontend/src/api/hooks/useExtractFromPhoto.ts` (neu):

```ts
useExtractFromPhoto() → UseMutationResult<ExtractedLabel, AxiosError, File>
```

Wrappt `POST /chemicals/extract-from-photo` als multipart. Pre-Resize via Canvas auf max. 2048 px Kantenlänge, JPEG Quality 0.85, bevor der File-Blob hochgeladen wird (gilt nur für Bilder > 2048 px Größe; HEIC wird durchgereicht, weil Browser-Canvas HEIC oft nicht dekodieren kann — Server validiert).

### 3.3 `ChemicalForm`-Änderungen (`frontend/src/components/drawer/ChemicalForm.tsx`)

- Header-Icon `CameraAltIcon` (MUI) im `EditDrawer.tsx` zwischen Titel und Close-Button. Klick triggert verstecktes `<input type="file" accept="image/*" capture="environment">`.
- State-Slots: `photoFile: File | null`, `photoPreviewUrl: string | null`, `extractedFields: Set<string>`, `extractedContainerPrefill: ContainerPrefill | null`.
- Auf File-Selection:
  1. `useExtractFromPhoto().mutate(file)`
  2. Bei Erfolg: `setName(...)`, `setCas(...)`, `extractedFields = new Set(["name", "cas"])`.
  3. `extractedContainerPrefill = {identifier, amount, unit, supplier_name, purity, purchased_at}` (nur die nicht-null Felder).
  4. Falls `cas` erkannt: `setQuery(cas)` und `onFetch()` automatisch triggern → bestehende PubChem-Anreicherung läuft.
- Photo-Strip oberhalb der Felder zeigt `photoPreviewUrl` + `confidence`-Label, wenn `photoFile` gesetzt.
- Auf jedem TextField: wenn der Feldname in `extractedFields` ist, `sx={{ '& .MuiOutlinedInput-root': { backgroundColor: theme.palette.accent.soft } }}` + `startAdornment: <CameraAltIcon fontSize="small" />`. `onChange` entfernt das Feld aus `extractedFields`.
- `onSubmit` (Create-Branch): nach erfolgreicher `create.mutateAsync(payload)`:
  - Wenn `photoFile` oder `extractedContainerPrefill` gesetzt → `drawer.open({ kind: "container-new", chemicalId: created.id, prefill: extractedContainerPrefill, photoFile })`.
  - Sonst: `onDone()` wie heute.
- Duplicate-Banner-Buttons (Zeile 318 und 344): die existierenden `drawer.open({ kind: "container-new", chemicalId })`-Aufrufe werden um `prefill` und `photoFile` erweitert, sofern vorhanden.

### 3.4 `ContainerForm`-Änderungen (`frontend/src/components/drawer/ContainerForm.tsx`)

- Header-Icon `CameraAltIcon` analog zu `ChemicalForm`. Bei diesem Form-Mode extrahiert die Foto-Aktion nur Container-Felder (CAS/Name werden ignoriert).
- `props` erhält `prefill?: ContainerPrefill` und `photoFile?: File` (aus dem `DrawerContext`).
- State-Init: wenn `prefill` vorhanden, werden die Felder befüllt und in `extractedFields` markiert.
- Photo-Strip oberhalb der Felder, wenn `photoFile` vorhanden.
- `onSubmit`: nach `create.mutateAsync(payload)` → wenn `photoFile` vorhanden, `useUploadContainerImage(created.id).mutateAsync(photoFile)` hinterher. Bei Image-Fehler: Inline-Banner „Container angelegt, Bild fehlgeschlagen [Erneut versuchen]". Container-Anlage wird nicht zurückgerollt.

### 3.5 Neuer Hook `useUploadContainerImage`

`frontend/src/api/hooks/useContainers.ts` (existierend, erweitert) bekommt:

```ts
useUploadContainerImage(containerId: string) → UseMutationResult<ContainerRead, AxiosError, File>
```

Wrappt `POST /containers/{id}/image` als multipart. Invalidiert nach Erfolg die Container-Query-Keys (`["container", containerId]`, `["containers", chemicalId]`).

### 3.6 Bild-Anzeige in der UI

`ContainerCard` / `ContainerDetailDrawer` (existierende Komponenten) bekommen einen optionalen `<img src={`/uploads/${container.image_path}`}>` Block, wenn `image_path` gesetzt ist. Größe: Thumb 64×64 in der Card, full-width im Drawer. Out of scope für v1: Lightbox / Vergrößerungs-Modal.

## Section 4 — Fehlerbehandlung

| Fehlerquelle | HTTP-Status | Body | Frontend-Reaktion |
|---|---|---|---|
| `CHAIMA_GEMINI_API_KEY` nicht gesetzt | 503 | `{"detail": "vision_not_configured"}` | Inline-Alert: „Foto-Erkennung in dieser Instanz deaktiviert" |
| Gemini-Timeout / 5xx | 502 | `{"detail": "vision_service_unavailable"}` | „Erkennung gerade nicht möglich — bitte manuell eingeben" |
| Bild > 10 MB | 413 | `{"detail": "image_too_large"}` | „Bild zu groß, max. 10 MB" |
| Falscher MIME-Type | 415 | `{"detail": "unsupported_image_format"}` | „Bildformat nicht unterstützt (JPEG/PNG/WebP/HEIC)" |
| Magic-Byte-Validation schlägt fehl | 415 | `{"detail": "invalid_image_data"}` | „Datei ist kein valides Bild" |
| Container nicht gefunden | 404 | Default | (in der Praxis unmöglich — geloggt) |
| Image-Upload-Permission verweigert | 403 | Default | „Du darfst dieses Gebinde nicht editieren" |
| Gemini liefert valides JSON aber alle Felder null | 200 | `ExtractedLabel(confidence="low", ...)` | Photo-Strip mit Warnhinweis „Keine Felder erkannt — bitte manuell eingeben", Felder bleiben leer |

**Frontend-Failure-Pfade:**
- Save-Sequenz bricht zwischen Chemical-Create und Container-Create → Chemical bleibt angelegt. Drawer zeigt Fehler mit Link zur Chemical-Detail-Seite. Kein Rollback (disproportional komplex).
- Save bricht zwischen Container-Create und Image-Upload → Container ist da, Bild fehlt. Banner mit „Erneut versuchen" → wiederholt nur den Image-Upload.

## Section 5 — Tests

### Backend

- `tests/test_services/test_vision.py` (neu): Service-Wrapper mit gemockter `google-genai`-Client-Antwort. Fälle: vollständig gefülltes JSON, partielles JSON, leere Antwort, Schema-Violation, API-Timeout, API-5xx, Key nicht gesetzt.
- `tests/test_api/test_chemicals_extract.py` (neu): Endpoint-Tests mit gemocktem Vision-Service. Cases:
  - 200 happy path (gemockter Erfolg liefert `ExtractedLabel`).
  - 415 falscher MIME (`text/plain`).
  - 415 invalid magic bytes (zufällige Bytes mit `image/jpeg` Content-Type).
  - 413 zu groß (>10 MB).
  - 502 vision-down (mock raises).
  - 503 key nicht konfiguriert.
  - 401/403 unauthenticated / wrong group.
- `tests/test_api/test_containers_image.py` (neu): `POST /containers/{id}/image`. Cases:
  - 200 happy path: setzt `container.image_path`, Datei existiert unter `uploads/<group_id>/`.
  - 200 idempotent: zweiter Upload überschreibt den Pfad.
  - 403 anderer User (nicht Creator, nicht Admin).
  - 403 anderer Group.
  - 404 unbekannter Container.
  - 415 falscher MIME.
  - 413 zu groß.

### Frontend

Keine neuen automatisierten Frontend-Tests (analog zu Orders-Feature). Smoke-Liste im Implementierungsplan:

1. Desktop: File-Picker öffnet sich beim Klick aufs Kamera-Icon.
2. Mobile: Direkt-Kamera öffnet sich (manuell auf einem echten Mobilgerät zu verifizieren).
3. Foto eines echten Etiketts → CAS und Name werden in `ChemicalForm` befüllt + markiert.
4. PubChem-Fetch wird nach Foto automatisch getriggert.
5. Nach Chemical-Create öffnet sich Container-Drawer mit Prefill und sichtbarer Foto-Thumb.
6. Container-Save → Bild ist in der Container-Detailansicht sichtbar.
7. Duplicate-Pfad: Foto einer bereits existierenden Chemikalie → `Add container`-Banner erscheint → Klick öffnet Container-Drawer mit Prefill und Foto.
8. Foto-Aktion direkt im `ContainerForm` (existing chemical context) → nur Container-Felder werden gefüllt, Chemical-Felder unberührt.
9. Bild > 10 MB → 413, inline Fehler.
10. `CHAIMA_GEMINI_API_KEY` leer → Kamera-Icon bleibt sichtbar, Klick zeigt 503-Banner „Foto-Erkennung in dieser Instanz deaktiviert" (kein zusätzlicher Config-Endpoint nötig).

## Section 6 — Known v1 Gaps

- **Image-Cleanup:** überschriebene Bilder bleiben auf der Platte. Cleanup-Cron oder sofortiges `unlink` ist Folge-Arbeit.
- **Authenticated Bild-URLs:** `/uploads` bleibt unauthenticated. Tightening ist ein eigener Refactor.
- **Confidence-basiertes Routing:** kein automatisches Eskalieren zu `gemini-2.5-pro` bei `confidence == "low"`. User editiert manuell.
- **Lightbox für Bilder:** Container-Detail zeigt das Bild full-width inline, keine Vergrößerung / Zoom.
- **HEIC im Browser:** Pre-Resize via Canvas funktioniert bei HEIC nicht zuverlässig — wir reichen HEIC unbearbeitet durch, Server validiert. Mobile Browser, die das Format direkt unterstützen, funktionieren; ältere Desktops sehen das hochgeladene Bild ggf. nicht in der Preview.
- **Konfidenz-Schwellwert für Prefill:** auch `confidence == "low"` füllt die Felder vor (markiert). Alternative wäre, bei `low` gar nicht zu prefillen — wir entscheiden uns für vorausfüllen + sichtbare Markierung als simpler UX.
