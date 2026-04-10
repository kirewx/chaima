import { Routes, Route } from "react-router-dom";
import { Typography, Box } from "@mui/material";

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
      <Route path="/" element={<Placeholder name="Search" />} />
      <Route path="/login" element={<Placeholder name="Login" />} />
    </Routes>
  );
}
