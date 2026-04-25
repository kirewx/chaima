export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

export interface UserRead {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  created_at: string;
  main_group_id: string | null;
  dark_mode: boolean;
}

export interface GroupRead {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface GroupCreate {
  name: string;
  description?: string | null;
}

export interface GroupUpdate {
  name?: string;
  description?: string | null;
}

export interface MemberRead {
  user_id: string;
  group_id: string;
  is_admin: boolean;
  joined_at: string;
  email: string;
}

export interface MemberAdd {
  email: string;
  is_admin?: boolean;
}

export interface MemberUpdate {
  is_admin: boolean;
}

export interface ChemicalCreate {
  name: string;
  cas?: string | null;
  smiles?: string | null;
  cid?: string | null;
  structure?: string | null;
  molar_mass?: number | null;
  density?: number | null;
  melting_point?: number | null;
  boiling_point?: number | null;
  comment?: string | null;
  is_secret?: boolean;
  synonyms?: string[];
  ghs_codes?: string[];
}

export interface ChemicalUpdate {
  name?: string | null;
  cas?: string | null;
  smiles?: string | null;
  cid?: string | null;
  structure?: string | null;
  molar_mass?: number | null;
  density?: number | null;
  melting_point?: number | null;
  boiling_point?: number | null;
  comment?: string | null;
  is_secret?: boolean;
  synonyms?: string[];
  ghs_codes?: string[];
}

export interface ChemicalRead {
  id: string;
  name: string;
  cas: string | null;
  smiles: string | null;
  cid: string | null;
  structure: string | null;
  molar_mass: number | null;
  density: number | null;
  melting_point: number | null;
  boiling_point: number | null;
  comment: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  is_secret: boolean;
  is_archived: boolean;
  archived_at: string | null;
  sds_path: string | null;
  synonym_names: string[];
}

export interface SynonymRead {
  id: string;
  chemical_id: string;
  name: string;
  category: string | null;
}

export interface ChemicalDetail extends ChemicalRead {
  synonyms: SynonymRead[];
  ghs_codes: GHSCodeRead[];
  hazard_tags: HazardTagRead[];
}

export interface ContainerCreate {
  location_id: string;
  supplier_id?: string | null;
  identifier: string;
  amount: number;
  unit: string;
  purity?: string | null;
  purchased_at?: string | null;
}

export interface ContainerUpdate {
  location_id?: string | null;
  supplier_id?: string | null;
  identifier?: string | null;
  amount?: number | null;
  unit?: string | null;
  purity?: string | null;
  purchased_at?: string | null;
  is_archived?: boolean | null;
}

export interface ContainerRead {
  id: string;
  chemical_id: string;
  location_id: string;
  supplier_id: string | null;
  identifier: string;
  amount: number;
  unit: string;
  purity: string | null;
  image_path: string | null;
  purchased_at: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

export interface GHSCodeRead {
  id: string;
  code: string;
  description: string;
  pictogram: string | null;
  signal_word: string | null;
}

export interface GHSCodeCreate {
  code: string;
  description: string;
  pictogram?: string | null;
  signal_word?: string | null;
}

export interface GHSCodeUpdate {
  code?: string | null;
  description?: string | null;
  pictogram?: string | null;
  signal_word?: string | null;
}

export interface HazardTagRead {
  id: string;
  name: string;
  description: string | null;
  group_id: string;
}

export interface HazardTagCreate {
  name: string;
  description?: string | null;
}

export interface HazardTagUpdate {
  name?: string | null;
  description?: string | null;
}

export interface IncompatibilityRead {
  id: string;
  tag_a_id: string;
  tag_b_id: string;
  reason: string | null;
}

export interface IncompatibilityCreate {
  tag_a_id: string;
  tag_b_id: string;
  reason?: string | null;
}

export interface SupplierRead {
  id: string;
  name: string;
  group_id: string;
  created_at: string;
  container_count: number;
}

export interface SupplierCreate {
  name: string;
}

export interface SupplierUpdate {
  name?: string | null;
}

export interface SupplierContainerRow {
  id: string;
  identifier: string;
  amount: number;
  unit: string;
  is_archived: boolean;
  chemical_id: string;
  chemical_name: string;
}

export type StorageKind = "building" | "room" | "cabinet" | "shelf";

export interface StorageLocationRead {
  id: string;
  name: string;
  kind: StorageKind;
  description: string | null;
  parent_id: string | null;
  color: string | null;
  created_at: string;
}

export interface StorageLocationCreate {
  name: string;
  kind: StorageKind;
  description?: string | null;
  parent_id?: string | null;
  color?: string | null;
}

export interface StorageLocationUpdate {
  name?: string | null;
  description?: string | null;
  parent_id?: string | null;
  color?: string | null;
}

export interface StorageLocationNode {
  id: string;
  name: string;
  kind: StorageKind;
  description: string | null;
  parent_id: string | null;
  color: string | null;
  container_count: number;
  children: StorageLocationNode[];
}

export interface ChemicalSearchParams {
  search?: string;
  hazard_tag_id?: string;
  ghs_code_id?: string;
  has_containers?: boolean;
  my_secrets?: boolean;
  location_id?: string;
  sort?: "name" | "created_at" | "updated_at" | "cas";
  order?: "asc" | "desc";
  limit?: number;
}

export interface ContainerSearchParams {
  search?: string;
  chemical_id?: string;
  location_id?: string;
  supplier_id?: string;
  is_archived?: boolean;
  sort?: "identifier" | "created_at" | "updated_at" | "amount" | "purchased_at";
  order?: "asc" | "desc";
  limit?: number;
}

export interface InviteInfo {
  group_name: string;
  expires_at: string;
  is_valid: boolean;
}

export interface InviteRead {
  id: string;
  group_id: string;
  token: string;
  created_by: string;
  expires_at: string;
  used_by: string | null;
  used_at: string | null;
}

export interface InviteAccept {
  email: string;
  password: string;
}

export interface PubChemGHSHit {
  code: string;
  description: string;
  signal_word: string | null;
  pictogram: string | null;
}

export interface PubChemLookupResult {
  cid: string;
  name: string;
  cas: string | null;
  molar_mass: number | null;
  smiles: string | null;
  synonyms: string[];
  ghs_codes: PubChemGHSHit[];
}

export interface PreviousImport {
  imported_at: string;
  imported_by_name: string;
  row_count: number;
}

export interface ImportPreviewResponse {
  columns: string[];
  rows: string[][];
  row_count: number;
  sheets: string[] | null;
  detected_mapping: Record<string, string>;
  previous_import: PreviousImport | null;
}

export interface ImportLocationMapping {
  source_text: string;
  location_id: string | null;
  new_location: { name: string; parent_id: string | null } | null;
}

export interface ImportChemicalGroup {
  canonical_name: string;
  canonical_cas: string | null;
  row_indices: number[];
}

export interface ImportCommitBody {
  file_name: string;
  column_mapping: Record<string, string>;
  quantity_unit_combined_column: string | null;
  columns: string[];
  rows: string[][];
  location_mapping: ImportLocationMapping[];
  chemical_groups: ImportChemicalGroup[];
}

export interface ImportWarning {
  chemical: string;
  row: number;
  details: string;
}

export interface ImportCommitResponse {
  created_chemicals: number;
  created_containers: number;
  created_locations: number;
  skipped_rows: { index: number; reason: string }[];
  warnings: ImportWarning[];
}

export type ImportTarget =
  | "name" | "cas" | "location_text" | "supplier_text" | "quantity" | "unit"
  | "quantity_unit_combined" | "purity" | "purchased_at"
  | "ordered_by" | "identifier" | "created_by_name" | "comment" | "ignore";

export const IMPORT_TARGETS: ImportTarget[] = [
  "name", "cas", "location_text", "supplier_text", "quantity", "unit",
  "quantity_unit_combined", "purity", "purchased_at", "ordered_by",
  "identifier", "created_by_name", "comment", "ignore",
];
