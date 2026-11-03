"""Names transcribed from the user's 6 x 7 specimen-box label photograph.

Preserves commercial names and abbreviations; this is not a mineral taxonomy.
"""
PHOTO_ROWS = [
    ['红血石', '青海翠', '虎眼石', '红条纹', '南红玛瑙', '熔岩', '黄玉'],
    ['黑碧玺', '白玉', '柠檬玉', '木化石', '黄纹石', '红东陵', '粉水晶'],
    ['红草莓', '紫斑马', '拉长石', '绿萤石', '绿眼石', '紫水晶', '太阳石'],
    ['天河石', '珊瑚', '白方解', '西瓜红', '黄萤石', '花绿', '木纹石'],
    ['闪光石', '黄方解', '鸡血石', '黄松', '茶晶', '青金石', '石膏'],
    ['绿东陵', '白松', '红碧玉', '白水晶', '磷灰石', '黄东陵', '黑曜石'],
]
SPECIMENS = [dict(id='s%02d' % (row * 7 + column + 1), name=name,
                  row=row + 1, column=column + 1)
             for row, names in enumerate(PHOTO_ROWS) for column, name in enumerate(names)]
BY_ID = {item['id']: item for item in SPECIMENS}
DEFAULT_MAPPING = {'black': 's42', 'red': 's38', 'white': 's39', 'gray': 's17',
                   'yellow': 's07', 'brown': 's03', 'green': 's36', 'blue': 's34', 'purple': 's20'}


def apply_name(classification, mapping):
    if classification['key'] == 'unknown':
        return classification
    specimen_id = mapping[classification['key']]
    name = BY_ID[specimen_id]['name']
    return dict(classification, name=name, display_name=name + '（颜色示例）',
                specimen_id=specimen_id, name_source='configured_color_mapping')
