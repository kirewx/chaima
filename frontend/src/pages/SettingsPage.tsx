import { useState } from "react";
import { Box, Stack } from "@mui/material";
import { useCurrentUser } from "../api/hooks/useAuth";
import { SettingsNav, type SettingsSectionKey, type NavItem } from "../components/settings/SettingsNav";
import { AccountSection } from "../components/settings/AccountSection";
import { GroupSection } from "../components/settings/GroupSection";
import { MembersInvitesSection } from "../components/settings/MembersInvitesSection";
import { HazardTagsSection } from "../components/settings/HazardTagsSection";
import { SuppliersSection } from "../components/settings/SuppliersSection";
import { BuildingsSection } from "../components/settings/BuildingsSection";
import { SystemSection } from "../components/settings/SystemSection";
import { ImportSection } from "../components/settings/ImportSection";
import { ChemicalsAdminSection } from "../components/settings/ChemicalsAdminSection";

export default function SettingsPage() {
  const { data: user } = useCurrentUser();
  const [active, setActive] = useState<SettingsSectionKey>("account");

  const isMember = Boolean(user?.main_group_id);
  const isSuperuser = Boolean(user?.is_superuser);

  const items: NavItem[] = [
    { key: "account", label: "Account", group: "PERSONAL", visible: true },
    { key: "group", label: "Group", group: "PERSONAL", visible: true },
    { key: "members", label: "Members & Invites", group: "GROUP ADMIN", visible: isMember },
    { key: "hazard-tags", label: "Hazard tags", group: "GROUP ADMIN", visible: isMember },
    { key: "suppliers", label: "Suppliers", group: "GROUP ADMIN", visible: isMember },
    { key: "import", label: "Import & Export", group: "GROUP ADMIN", visible: isMember },
    { key: "chemicals-admin", label: "Chemicals", group: "GROUP ADMIN", visible: isMember },
    { key: "buildings", label: "Buildings", group: "SYSTEM", visible: isSuperuser },
    { key: "system", label: "System", group: "SYSTEM", visible: isSuperuser },
  ];

  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={{ md: 3 }}>
      <SettingsNav items={items} active={active} onSelect={setActive} />
      <Box sx={{ flex: 1, minWidth: 0 }}>
        {active === "account" && <AccountSection />}
        {active === "group" && <GroupSection />}
        {active === "members" && isMember && user?.main_group_id && (
          <MembersInvitesSection groupId={user.main_group_id} />
        )}
        {active === "hazard-tags" && isMember && user?.main_group_id && (
          <HazardTagsSection groupId={user.main_group_id} />
        )}
        {active === "suppliers" && isMember && user?.main_group_id && (
          <SuppliersSection groupId={user.main_group_id} />
        )}
        {active === "import" && isMember && user?.main_group_id && (
          <ImportSection groupId={user.main_group_id} />
        )}
        {active === "chemicals-admin" && isMember && user?.main_group_id && (
          <ChemicalsAdminSection groupId={user.main_group_id} />
        )}
        {active === "buildings" && isSuperuser && <BuildingsSection />}
        {active === "system" && isSuperuser && <SystemSection />}
      </Box>
    </Stack>
  );
}
