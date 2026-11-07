"""Organize public material lists while retaining every source pointer."""

import re


def material_groups(refs):
    """Return sections of reference indices, with the display excerpt first."""
    sections = {'史料摘录与摘要': [], '裁决依据与采用说明': []}
    books = [
        {name.split('·', 1)[0] for name in re.findall(r'《([^《》]+)》', ref['source_title'])}
        for ref in refs
    ]
    decision_texts = {
        ref['exact_quote'] for ref in refs if ref['source_kind'].startswith(('裁决依据', '项目采用说明'))
    }
    for index, ref in enumerate(refs):
        decision = ref['source_kind'].startswith(('裁决依据', '项目采用说明')) or (
            ref['field_path'][-1] == 'summary' and (
                ref['exact_quote'] in decision_texts
                or ref.get('display_with_field_path', [None])[0] == 'state_adjudication'
            )
        )
        groups = sections['裁决依据与采用说明' if decision else '史料摘录与摘要']
        for group in groups:
            same_source = all(
                ref['source_title'] == refs[other]['source_title'] or bool(books[index] & books[other])
                for other in group
            )
            if ref['exact_quote'] == refs[group[0]]['exact_quote'] and (decision or same_source):
                group.append(index)
                break
        else:
            groups.append([index])

    excerpts = sections['史料摘录与摘要']
    # Explicit same-passage decisions are authored on the shorter reference.
    reviewed = {}
    for index, ref in enumerate(refs):
        if 'display_with_field_path' in ref:
            targets = [
                other for other, target in enumerate(refs)
                if target['axis'] == ref.get('display_with_axis', ref['axis'])
                and target['field_path'] == ref['display_with_field_path']
            ]
            if len(targets) != 1 or targets[0] == index:
                raise ValueError(f"材料归并定位无效：{ref['ruler_id']} / {ref['field_path']}")
            reviewed[index] = targets[0]
    for index, target in reviewed.items():
        source_section = next(groups for groups in sections.values() if any(index in group for group in groups))
        origin = next(group for group in source_section if index in group)
        destination = next((group for group in source_section if target in group), None)
        if destination is None or target in reviewed or origin is destination:
            raise ValueError(f"材料归并须指向同类的另一条材料：{refs[index]['ruler_id']} / {refs[index]['field_path']}")
        destination.extend(origin)
        source_section.remove(origin)

    # The C4 negative-tail record can reproduce the civilian-cost basis
    # verbatim before adding overlap and pricing decisions.
    decisions = sections['裁决依据与采用说明']
    tails = [group for group in decisions if refs[group[0]]['axis'] == 'C4'
             and refs[group[0]]['field_path'] == ['negative_tail_adjudication_reason']]
    for tail in tails:
        text_with_tail = refs[tail[0]]['exact_quote']
        for group in decisions[:]:
            ref = refs[group[0]]
            if (ref['axis'] == 'C4'
                    and ref['field_path'] == ['active_civilian_cost_review', 'choice_and_civilian_basis']
                    and text_with_tail.startswith(ref['exact_quote'] + ' 去重：')):
                tail.extend(group)
                decisions.remove(group)

    # Only fold short excerpts into a longer passage from the same named work.
    # Keep all locators, including the one attached to the shorter excerpt.
    text = [re.sub(r'[\W_]+', '', ref['exact_quote']) for ref in refs]
    for group in sorted(excerpts, key=lambda group: len(text[group[0]])):
        short = group[0]
        if len(text[short]) < 8 or len(books[short]) != 1:
            continue
        matches = [
            other for other in excerpts
            if len(text[other[0]]) > len(text[short])
            and books[short] <= books[other[0]]
            and text[short] in text[other[0]]
        ]
        if len(matches) == 1:
            matches[0].extend(group)
            excerpts.remove(group)
    return {label: groups for label, groups in sections.items() if groups}
