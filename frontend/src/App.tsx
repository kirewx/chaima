import { Routes, Route, Navigate } from "react-router-dom";
import { Typography, Box } from "@mui/material";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import SearchPage from "./pages/SearchPage";

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
          <Route path="/add" element={<Placeholder name="Add Chemical" />} />
          <Route path="/chemicals/:id/edit" element={<Placeholder name="Edit Chemical" />} />
          <Route path="/containers/new" element={<Placeholder name="Add Container" />} />
          <Route path="/containers/:id/edit" element={<Placeholder name="Edit Container" />} />
          <Route path="/storage" element={<Placeholder name="Storage" />} />
          <Route path="/storage/:id" element={<Placeholder name="Storage Detail" />} />
          <Route path="/settings" element={<Placeholder name="Settings" />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
