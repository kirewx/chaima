import { useRef, useState, type ReactNode, type TouchEvent } from "react";
import { Box, IconButton, useMediaQuery, useTheme } from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";

const THRESHOLD = 80;

interface SwipeableRowProps {
  children: ReactNode;
  onSwipeLeft?: () => void;
  onSwipeRight?: () => void;
  leftLabel?: string;
  rightLabel?: string;
}

export default function SwipeableRow({ children, onSwipeLeft, onSwipeRight, leftLabel = "Archive", rightLabel = "Add" }: SwipeableRowProps) {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const startX = useRef(0);
  const [offsetX, setOffsetX] = useState(0);

  const handleTouchStart = (e: TouchEvent) => { startX.current = e.touches[0].clientX; };
  const handleTouchMove = (e: TouchEvent) => {
    const diff = e.touches[0].clientX - startX.current;
    if (onSwipeLeft && diff < 0) setOffsetX(Math.max(diff, -THRESHOLD - 20));
    else if (onSwipeRight && diff > 0) setOffsetX(Math.min(diff, THRESHOLD + 20));
  };
  const handleTouchEnd = () => {
    if (offsetX < -THRESHOLD && onSwipeLeft) onSwipeLeft();
    else if (offsetX > THRESHOLD && onSwipeRight) onSwipeRight();
    setOffsetX(0);
  };

  if (isDesktop) {
    return (
      <Box sx={{
        position: "relative",
        borderRadius: 2,
        "&:hover .desktop-actions": { opacity: 1 },
      }}>
        {children}
        {(onSwipeRight || onSwipeLeft) && (
          <Box className="desktop-actions" sx={{
            position: "absolute", top: 0, right: 8, bottom: 0,
            display: "flex", alignItems: "center", gap: 0.5,
            opacity: 0, transition: "opacity 0.15s",
          }}>
            {onSwipeRight && (
              <IconButton size="small" onClick={(e) => { e.stopPropagation(); onSwipeRight(); }}
                sx={{ bgcolor: "success.main", color: "#000", "&:hover": { bgcolor: "success.dark" }, width: 32, height: 32 }}
                title={rightLabel}>
                <AddIcon sx={{ fontSize: 18 }} />
              </IconButton>
            )}
            {onSwipeLeft && (
              <IconButton size="small" onClick={(e) => { e.stopPropagation(); onSwipeLeft(); }}
                sx={{ bgcolor: "error.main", color: "#fff", "&:hover": { bgcolor: "error.dark" }, width: 32, height: 32 }}
                title={leftLabel}>
                <DeleteIcon sx={{ fontSize: 18 }} />
              </IconButton>
            )}
          </Box>
        )}
      </Box>
    );
  }

  return (
    <Box sx={{ position: "relative", overflow: "hidden", borderRadius: 2 }}>
      {onSwipeLeft && offsetX < 0 && (
        <Box sx={{ position: "absolute", top: 0, right: 0, bottom: 0, width: THRESHOLD, bgcolor: "error.main", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 0.5 }}>
          <DeleteIcon sx={{ fontSize: 20 }} />
          <Box sx={{ fontSize: 10 }}>{leftLabel}</Box>
        </Box>
      )}
      {onSwipeRight && offsetX > 0 && (
        <Box sx={{ position: "absolute", top: 0, left: 0, bottom: 0, width: THRESHOLD, bgcolor: "success.main", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 0.5, color: "#000" }}>
          <AddIcon sx={{ fontSize: 20 }} />
          <Box sx={{ fontSize: 10 }}>{rightLabel}</Box>
        </Box>
      )}
      <Box onTouchStart={handleTouchStart} onTouchMove={handleTouchMove} onTouchEnd={handleTouchEnd}
        sx={{ position: "relative", zIndex: 1, transform: `translateX(${offsetX}px)`, transition: offsetX === 0 ? "transform 0.2s ease-out" : "none" }}>
        {children}
      </Box>
    </Box>
  );
}
