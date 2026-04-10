import { useRef, useState, type ReactNode, type TouchEvent } from "react";
import { Box } from "@mui/material";
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

  return (
    <Box sx={{ position: "relative", overflow: "hidden", borderRadius: 2 }}>
      {onSwipeLeft && (
        <Box sx={{ position: "absolute", top: 0, right: 0, bottom: 0, width: THRESHOLD, bgcolor: "error.main", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 0.5 }}>
          <DeleteIcon sx={{ fontSize: 20 }} />
          <Box sx={{ fontSize: 10 }}>{leftLabel}</Box>
        </Box>
      )}
      {onSwipeRight && (
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
