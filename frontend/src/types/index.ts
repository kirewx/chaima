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
  image_path: string | null;
  comment: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
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
  purchased_at?: string | null;
}

export interface ContainerUpdate {
  location_id?: string | null;
  supplier_id?: string | null;
  identifier?: string | null;
  amount?: number | null;
  unit?: string | null;
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
}

export interface SupplierCreate {
  name: string;
}

export interface SupplierUpdate {
  name?: string | null;
}

export interface StorageLocationRead {
  id: string;
  name: string;
  description: string | null;
  parent_id: string | null;
  created_at: string;
}

export interface StorageLocationCreate {
  name: string;
  description?: string | null;
  parent_id?: string | null;
}

export interface StorageLocationUpdate {
  name?: string | null;
  description?: string | null;
  parent_id?: string | null;
}

export interface StorageLocationNode {
  id: string;
  name: string;
  description: string | null;
  children: StorageLocationNode[];
}

export interface ChemicalSearchParams {
  search?: string;
  hazard_tag_id?: string;
  ghs_code_id?: string;
  has_containers?: boolean;
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
