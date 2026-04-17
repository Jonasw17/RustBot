"""
grid_coordinates.py
────────────────────────────────────────────────────────────────────────────
Helper functions for converting Rust world coordinates to grid references.

Rust maps use a grid system with columns (A-Z, AA-ZZ, etc.) and rows (0-29).
The grid size varies based on map size.
"""

import math
from typing import Tuple


def get_grid_size(map_size: int) -> Tuple[int, int]:
    """
    Calculate grid dimensions based on map size.
    
    Args:
        map_size: Map size (e.g., 3000, 4000, 4500)
    
    Returns:
        (grid_width, grid_height) - dimensions of each grid cell
    """
    # Rust maps are typically square
    # Standard grids are 26x26 for most maps (A-Z, 0-25)
    # Larger maps may extend to AA, AB, etc.
    
    # Most common: 30 rows (0-29), variable columns
    grid_rows = 30
    
    # Calculate grid columns based on map size
    # Typical: 4500 = 30x30, 4000 = 27x27, 3000 = 20x20
    grid_cols = int(math.ceil(map_size / 150))  # ~150 units per grid cell
    
    cell_width = map_size / grid_cols
    cell_height = map_size / grid_rows
    
    return (cell_width, cell_height)


def column_to_letter(col: int) -> str:
    """
    Convert column number to letter(s).
    
    0 -> A, 25 -> Z, 26 -> AA, 27 -> AB, etc.
    
    Args:
        col: Column index (0-based)
    
    Returns:
        Column letter(s)
    """
    result = ""
    col += 1  # Make 1-based for the algorithm
    
    while col > 0:
        col -= 1
        result = chr(ord('A') + (col % 26)) + result
        col //= 26
    
    return result


def world_to_grid(x: float, y: float, map_size: int) -> str:
    """
    Convert world coordinates to grid reference.
    
    Args:
        x: World X coordinate (0 to map_size)
        y: World Y coordinate (0 to map_size)
        map_size: Map size (e.g., 4500)
    
    Returns:
        Grid reference string (e.g., "K15", "AA22")
    """
    # Get grid cell dimensions
    cell_width, cell_height = get_grid_size(map_size)
    
    # Calculate grid column and row
    # X axis = columns (A-Z, AA-ZZ, etc.)
    # Y axis = rows (0-29)
    col = int(x / cell_width)
    row = int(y / cell_height)
    
    # Clamp to valid range
    max_cols = int(map_size / cell_width)
    max_rows = 30
    
    col = max(0, min(col, max_cols - 1))
    row = max(0, min(row, max_rows - 1))
    
    # Convert to grid reference
    col_letter = column_to_letter(col)
    
    return f"{col_letter}{row}"


def grid_to_world(grid_ref: str, map_size: int) -> Tuple[float, float]:
    """
    Convert grid reference to approximate world coordinates (center of grid).
    
    Args:
        grid_ref: Grid reference (e.g., "K15", "AA22")
        map_size: Map size
    
    Returns:
        (x, y) world coordinates
    """
    # Parse grid reference
    col_str = ""
    row_str = ""
    
    for char in grid_ref:
        if char.isalpha():
            col_str += char
        elif char.isdigit():
            row_str += char
    
    if not col_str or not row_str:
        raise ValueError(f"Invalid grid reference: {grid_ref}")
    
    # Convert column letters to number
    col = 0
    for char in col_str:
        col = col * 26 + (ord(char.upper()) - ord('A') + 1)
    col -= 1  # Convert back to 0-based
    
    row = int(row_str)
    
    # Get grid cell dimensions
    cell_width, cell_height = get_grid_size(map_size)
    
    # Calculate center of grid cell
    x = (col + 0.5) * cell_width
    y = (row + 0.5) * cell_height
    
    return (x, y)


# Example usage
if __name__ == "__main__":
    # Test conversions
    map_size = 4500
    
    test_coords = [
        (0, 0),
        (4500, 4500),
        (2250, 2250),
        (1000, 1500),
        (3500, 2800),
    ]
    
    print(f"Map size: {map_size}")
    print(f"Grid dimensions: {get_grid_size(map_size)}")
    print()
    
    for x, y in test_coords:
        grid = world_to_grid(x, y, map_size)
        back_x, back_y = grid_to_world(grid, map_size)
        print(f"({x:4}, {y:4}) -> {grid:4} -> ({back_x:6.1f}, {back_y:6.1f})")
