# -*- coding: utf-8 -*-
"""打 WorkBuddy 开放平台的上架包：dist/workbuddy/quafu.zip，zip 根目录是 quafu/。

主版本的 SKILL.md 只放 name + description（Claude Code、Codex、OpenCode 通用）；
WorkBuddy 另要 description_zh、description_en、version、author，这些字段只加在上架包里，
版本号取自 .claude-plugin/plugin.json，不在第二处手写。

    python3 tools/build_workbuddy.py                 # 打包并校验
    python3 tools/build_workbuddy.py --author 某某    # author 写认证主体名称
"""
import argparse
import io
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, 'skills', 'quafu')
MAX_BYTES = 3 * 1024 * 1024          # 开放平台技能包上限 3MB
REQUIRED = ('description', 'description_zh', 'description_en', 'version', 'author')
SKIP = ('__pycache__', '.pyc', '.DS_Store')

DISPLAY_NAME = 'QUAFU'
DESCRIPTION_ZH = ('让 AI 替你在 QUAFU 量子计算云平台上写并运行量子程序：网页授权登录，10 个内置经典算法，'
                  '模拟器与超导量子真机，异步取结果，对比理想结果讲清噪声，生成可交互的结果网页。')
DESCRIPTION_EN = ('Let your AI agent write and run quantum programs on the QUAFU quantum cloud - browser login, '
                  '10 built-in algorithms, simulators and superconducting devices, async results, '
                  'noise analysis and interactive result pages.')


def plugin_meta():
    return json.load(open(os.path.join(ROOT, '.claude-plugin', 'plugin.json'), encoding='utf-8'))


def workbuddy_skill_md(author):
    src = open(os.path.join(SKILL, 'SKILL.md'), encoding='utf-8').read()
    m = re.match(r'^---\nname: (.+)\ndescription: (.+)\n---\n', src)
    if not m:
        sys.exit('SKILL.md 的 frontmatter 不是 name + description 两行')
    fields = [('name', m.group(1)), ('display_name', DISPLAY_NAME), ('display_name_en', DISPLAY_NAME),
              ('description', m.group(2)), ('description_zh', DESCRIPTION_ZH),
              ('description_en', DESCRIPTION_EN), ('version', plugin_meta()['version']), ('author', author)]
    head = '---\n' + ''.join('%s: %s\n' % kv for kv in fields) + '---\n'
    return head + src[m.end():]


def check_frontmatter(text):
    """按开放平台的要求检查：必填字段齐全；值写成不带引号的 YAML 纯量（冒号后有空格、不用引号）。"""
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        return ['没有 frontmatter']
    errors, keys = [], {}
    for line in m.group(1).split('\n'):
        k, sep, v = line.partition(': ')
        if not sep or not re.match(r'^[a-z_-]+$', k):
            errors.append('格式不对：%r' % line)
            continue
        keys[k] = v
        if ': ' in v or v.endswith(':') or ' #' in v:
            errors.append('%s 的值里有「: 」或「 #」，YAML 会解析错' % k)
        if v[:1] in '"\'“”‘’[{&*!|>%@`' or any(c in v for c in '“”‘’'):
            errors.append('%s 的值不要用引号或 YAML 特殊字符开头' % k)
    errors += ['缺必填字段 %s' % k for k in REQUIRED if not keys.get(k)]
    if not re.match(r'^\d+\.\d+\.\d+$', keys.get('version', '')):
        errors.append('version 不是 x.y.z')
    return errors


def build(out, author):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for d, dirs, files in os.walk(SKILL):
            dirs[:] = sorted(x for x in dirs if x not in SKIP)
            for f in sorted(files):
                if f.endswith(SKIP):
                    continue
                path = os.path.join(d, f)
                arc = 'quafu/' + os.path.relpath(path, SKILL).replace(os.sep, '/')
                if arc == 'quafu/SKILL.md':
                    z.writestr(arc, workbuddy_skill_md(author))
                else:
                    z.write(path, arc)
    data = buf.getvalue()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(data)
    return out


def verify(path):
    errors = []
    if os.path.getsize(path) > MAX_BYTES:
        errors.append('zip 超过 3MB')
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if any(not n.startswith('quafu/') or '..' in n for n in names):
            errors.append('zip 里有不在 quafu/ 下的文件')
        if 'quafu/SKILL.md' not in names:
            errors.append('缺 quafu/SKILL.md')
        else:
            errors += check_frontmatter(z.read('quafu/SKILL.md').decode('utf-8'))
    return errors


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--author', default=plugin_meta()['author']['name'], help='认证主体名称（默认取 plugin.json）')
    p.add_argument('--out', default=os.path.join(ROOT, 'dist', 'workbuddy', 'quafu.zip'))
    a = p.parse_args(argv)
    path = build(a.out, a.author)
    errors = verify(path)
    for e in errors:
        print('错误：' + e, file=sys.stderr)
    if errors:
        return 1
    print('%s  %.1f KB  version %s  author %s' % (path, os.path.getsize(path) / 1024,
                                                plugin_meta()['version'], a.author))
    return 0


if __name__ == '__main__':
    sys.exit(main())
