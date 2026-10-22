"""Public reading entry for fourth-item A; implementation is shared with the other axis."""
from .fourth_item_ab_public import (
    AxisReading, CURVE_SOURCE, SCOPE_SOURCE, METHOD, SCALE, INTERNAL,
    markdown_reading, source_label,
)

TITLE = '国家共同体与社会整合'
BOUNDARY = '只评价不同区域、族群和身份群体的实际参与、接纳、排斥及共同体关系变化。军事征服、行政设置、直接人身伤害和教育文化成果分别由相应项目承担，同一后果不重复计算。'

_reading = AxisReading('A')
SCHEMA = _reading.schema
package_reading = _reading.package_reading
axis_reading = _reading.axis_reading
verify_readings = _reading.verify_readings
