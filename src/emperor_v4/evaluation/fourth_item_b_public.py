"""Public reading entry for fourth-item B; implementation is shared with the other axis."""
from .fourth_item_ab_public import (
    AxisReading, CURVE_SOURCE, SCOPE_SOURCE, METHOD, SCALE, INTERNAL,
    markdown_reading, source_label,
)

TITLE = '教育可及与人才流动'
BOUNDARY = '只评价实际教学、学习机会和人才流动的独立变化，不重复计算选官制度、当期官僚质量及知识文化成果。'

_reading = AxisReading('B')
SCHEMA = _reading.schema
package_reading = _reading.package_reading
axis_reading = _reading.axis_reading
verify_readings = _reading.verify_readings
