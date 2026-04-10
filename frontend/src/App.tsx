import { Routes, Route, Navigate } from "react-router-dom";
import { Typography, Box } from "@mui/material";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import SearchPage from "./pages/SearchPage";
import ChemicalForm from "./pages/ChemicalForm";
import ContainerForm from "./pages/ContainerForm";
import StoragePage from "./pages/StoragePage";
import SettingsPage from "./pages/SettingsPage";

function Placeholder({ name }: { name: string }) {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5">{name}</Typography>
    </Box>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<SearchPage />} />
          <Route path="/add" element={<ChemicalForm />} />
          <Route path="/chemicals/:id/edit" element={<ChemicalForm />} />
          <Route path="/containers/new" element={<ContainerForm />} />
          <Route path="/containers/:id/edit" element={<Placeholder name="Edit Container" />} />
          <Route path="/storage" element={<StoragePage />} />
          <Route path="/storage/:id" element={<StoragePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
