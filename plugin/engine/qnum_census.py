"""题号普查：按 章/专题/题型 收题本 raw 文本的行首题号，打印缺号。

用途：派提取子代理之前跑一遍，把“缺号清单”写进 BOUNDARIES 与子代理 context，
让提取阶段就按选项反查补齐（OCR 最常丢的就是题号行）。定稿时再跑一遍做验收。

用法：
  python scripts/qnum_census.py <OCR原始目录> 143 228
  python scripts/qnum_census.py <OCR原始目录> 40 62 --prefix q_pdf --suffix _L,_R
"""
import argparse
import os
import re
import sys
from collections import defaultdict

QTYPE_RE = re.compile(
    r'^([一二三四五六七八九])\s*[、.．]\s*'
    r'(单项选择题|多项选择题|判断题|填空题|辨析题|简答题|论述题|案例分析题|材料分析题)'
)
TOPIC_RE = re.compile(r'^专题([一二三四五六七八九])')
CHAPTER_RE = re.compile(r'^第([一二三四五六七八九十]{1,3})章')
NUM_RE = re.compile(r'^(\d{1,3})\s*[.．]')


def iter_lines(raw_dir, lo, hi, prefix, suffixes):
    """按页序产出 (文件名, 行文本)；缺页/缺半页自动跳过。"""
    for p in range(lo, hi + 1):
        for suf in suffixes:
            fp = os.path.join(raw_dir, f"{prefix}{p:03d}{suf}.txt")
            if not os.path.exists(fp):
                continue
            for ln in open(fp, encoding='utf-8').read().splitlines():
                yield os.path.basename(fp), ln.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('raw_dir')
    ap.add_argument('lo', type=int)
    ap.add_argument('hi', type=int)
    ap.add_argument('--prefix', default='q')
    ap.add_argument('--suffix', default='',
                    help='切半册用 ,_L,_R ；单页册留空')
    a = ap.parse_args()
    suffixes = ['' if s == '' else s for s in a.suffix.split(',')] if a.suffix else ['']

    chapter = topic = qtype = None
    rows = defaultdict(list)   # (章, 专题, 题型) -> [题号]
    for fname, s in iter_lines(a.raw_dir, a.lo, a.hi, a.prefix, suffixes):
        if CHAPTER_RE.match(s):
            chapter = CHAPTER_RE.match(s).group(1) + '章'
            topic = qtype = None
            print(f"[章头] {fname}: {s}")
            continue
        m = TOPIC_RE.match(s)
        if m:
            topic, qtype = s, None
            print(f"[专题] {fname}: {s}")
            continue
        m = QTYPE_RE.match(s)
        if m:
            qtype = m.group(2)
            print(f"[题型] {fname}: {s}")
            continue
        if not (chapter and topic and qtype):
            continue
        m = NUM_RE.match(s)
        if m:
            rows[(chapter, topic, qtype)].append((int(m.group(1)), fname))

    print("\n===== 普查结果 =====")
    total = 0
    for k in sorted(rows, key=lambda x: (x[0], x[1], x[2])):
        nums = [n for n, _ in rows[k]]
        total += len(nums)
        uniq = sorted(set(nums))
        gaps = [i for i in range(1, max(uniq) + 1) if i not in uniq]
        dup = sorted({n for n in nums if nums.count(n) > 1})
        flag = ''
        if gaps:
            flag += f" 缺{gaps}"
        if dup:
            flag += f" 重复{dup}"
        print(f"{k[0]} {k[1]} {k[2]}: {len(nums)}题 max={max(uniq)}{flag}")
    print(f"\n合计 {total} 题（含重复计数）")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
