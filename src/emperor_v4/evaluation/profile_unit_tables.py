"""Lossless ordered tables for retained unit-disposition records."""
from copy import deepcopy
import json

STORAGE = 'profile-unit-column-table-v1'
LIST_STORAGE = 'profile-unit-column-table-v2'
MARKER = 'unit_storage'
COLUMNS = 'unit_columns'
ROWS = 'unit_rows'
DICTIONARIES = 'unit_value_catalogs'
LIST_DICTIONARIES = 'unit_string_list_catalogs'
KEYS = {MARKER, COLUMNS, ROWS, DICTIONARIES, LIST_DICTIONARIES}
C1_SCHEMA = 'profile-c1-unit-disposition-audit-v1'
M4_SCHEMA = 'profile-m4-unit-disposition-audit-v1'
TABLE_SCHEMAS = frozenset({
    C1_SCHEMA, M4_SCHEMA,
    'profile-c2-unit-disposition-audit-v4',
    'profile-c3-unit-disposition-audit-v1',
    'emperor-profile-c5-unit-disposition-formal-audit-v2',
})


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def expand_unit_table(payload):
    if not KEYS & payload.keys():
        return payload
    version = payload.get(MARKER)
    if version not in (STORAGE, LIST_STORAGE) or 'units' in payload:
        raise ValueError('单元表存储版本无效或混用对象格式')
    if version == STORAGE and LIST_DICTIONARIES in payload:
        raise ValueError('单元表版本与列表目录不符')
    columns = payload.get(COLUMNS)
    rows = payload.get(ROWS)
    dictionaries = payload.get(DICTIONARIES)
    list_dictionaries = payload.get(LIST_DICTIONARIES) if version == LIST_STORAGE else {}
    if (not isinstance(columns, list) or not columns
            or any(not isinstance(k, str) or not k for k in columns)
            or len(set(columns)) != len(columns)
            or not isinstance(rows, list) or any(not isinstance(r, list) or len(r) != len(columns) for r in rows)):
        raise ValueError('单元表列名或行宽无效')
    if not isinstance(dictionaries, dict) or not set(dictionaries) <= set(columns):
        raise ValueError('单元表值目录列无效')
    if (not isinstance(list_dictionaries, dict) or not set(list_dictionaries) <= set(columns)
            or set(list_dictionaries) & set(dictionaries) or (version == LIST_STORAGE and not list_dictionaries)):
        raise ValueError('单元表列表目录列无效')
    catalogs = {**dictionaries, **list_dictionaries}
    for values in catalogs.values():
        if (not isinstance(values, list) or not values or any(not isinstance(v, str) for v in values)
                or len(set(values)) != len(values)):
            raise ValueError('单元表值目录无效或重复')
    used = {key: set() for key in catalogs}
    units = []
    for row in rows:
        unit = {}
        for column, value in zip(columns, row, strict=True):
            if column in dictionaries:
                if type(value) is not int or not 0 <= value < len(dictionaries[column]):
                    raise ValueError('单元表值引用越界或类型无效')
                used[column].add(value)
                value = dictionaries[column][value]
            elif column in list_dictionaries:
                if (not isinstance(value, list) or any(type(ref) is not int or not 0 <= ref < len(list_dictionaries[column]) for ref in value)):
                    raise ValueError('单元表列表值引用越界或类型无效')
                used[column].update(value)
                value = [list_dictionaries[column][ref] for ref in value]
            unit[column] = deepcopy(value)
        units.append(unit)
    if any(used[key] != set(range(len(values))) for key, values in catalogs.items()):
        raise ValueError('单元表值目录存在未用条目')
    return {('units' if key == ROWS else key): (units if key == ROWS else deepcopy(value))
            for key, value in payload.items() if key not in {MARKER, COLUMNS, DICTIONARIES, LIST_DICTIONARIES}}


def compact_unit_table(payload, *, list_columns=()):
    if KEYS & payload.keys():
        expand_unit_table(payload)
        return deepcopy(payload)
    units = payload.get('units')
    if not isinstance(units, list) or any(not isinstance(u, dict) for u in units):
        raise ValueError('单元表输入须为完整对象列表')
    # Mixed layouts stay inline: absent fields must never become null defaults.
    if not units or not units[0] or any(list(u) != list(units[0]) for u in units):
        return deepcopy(payload)
    columns = list(units[0])
    if (not isinstance(list_columns, (list, tuple)) or any(not isinstance(k, str) or k not in columns for k in list_columns)
            or len(set(list_columns)) != len(list_columns)):
        raise ValueError('单元表列表压缩字段无效')
    rows = [[deepcopy(unit[key]) for key in columns] for unit in units]
    dictionaries = {}
    for index, key in enumerate(columns):
        values = [unit[key] for unit in units]
        if not all(isinstance(value, str) for value in values):
            continue
        unique = list(dict.fromkeys(values))
        lookup = {value: i for i, value in enumerate(unique)}
        refs = [lookup[value] for value in values]
        if len(_encoded(values)) <= len(_encoded(unique)) + len(_encoded(refs)) + len(_encoded(key)) + 2:
            continue
        dictionaries[key] = unique
        for row, ref in zip(rows, refs, strict=True):
            row[index] = ref
    list_dictionaries = {}
    for key in list_columns:
        values = [unit[key] for unit in units]
        if not all(isinstance(value, list) and all(isinstance(item, str) for item in value) for value in values):
            continue
        unique = list(dict.fromkeys(item for value in values for item in value))
        lookup = {value: i for i, value in enumerate(unique)}
        refs = [[lookup[value] for value in items] for items in values]
        if not unique or len(_encoded(values)) <= len(_encoded(unique)) + len(_encoded(refs)) + len(_encoded(key)) + 2:
            continue
        list_dictionaries[key] = unique
        index = columns.index(key)
        for row, ref in zip(rows, refs, strict=True):
            row[index] = ref
    result = {('unit_rows' if key == 'units' else key): (rows if key == 'units' else deepcopy(value))
              for key, value in payload.items()}
    result.update({MARKER: LIST_STORAGE if list_dictionaries else STORAGE, COLUMNS: columns, DICTIONARIES: dictionaries})
    if list_dictionaries:
        result[LIST_DICTIONARIES] = list_dictionaries
    return result if len(_encoded(result)) < len(_encoded(payload)) else deepcopy(payload)
