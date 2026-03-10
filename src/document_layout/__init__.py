from .cells import BlockType, FieldStyle, FieldDef, RowDef, BlockVariant, DocumentLayout, build_random_layout
from .packing import solve_layout, LayoutResult, BlockPlacement, FieldPlacement
from .renderer import render_layout, save_metadata, fill_values
