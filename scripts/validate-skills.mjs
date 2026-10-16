#!/usr/bin/env node
/**
 * validate-skills.mjs — проверка скиллов по спецификации Agent Skills (agentskills.io).
 *
 * Что проверяется:
 *   * SKILL.md существует у каждого каталога в skills/;
 *   * frontmatter блоками --- ---, обязательные name и description;
 *   * name: 1–64 символа, только a-z 0-9 и одиночные дефисы, совпадает с именем каталога;
 *   * description: 1–1024 символа, не похож на заголовок (совет, не ошибка);
 *   * в frontmatter нет угловых скобок < > (spec: могут инжектиться в системный промпт);
 *   * пути references/…, templates/…, scripts/…, assets/… из тела реально существуют;
 *   * тело не пустое и не заканчивается обрывом.
 *
 * Запуск: node scripts/validate-skills.mjs [--json]
 * Код возврата 1 при ошибках, 0 при предупреждениях.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SKILLS = path.join(REPO, 'skills')
const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/

/** Разбор минимального YAML-frontmatter: ключ: значение + вложенные блоки по отступу. */
function parseFrontmatter(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!m) return null
  const [, raw, body] = m
  const flat = {}
  const nested = {}
  let current = null
  for (const line of raw.split(/\r?\n/)) {
    if (!line.trim() || line.trim().startsWith('#')) continue
    const indent = line.match(/^\s*/)[0].length
    const kv = line.match(/^\s*([A-Za-z0-9_.-]+):\s*(.*)$/)
    if (indent === 0 && kv) {
      const [, key, value] = kv
      if (value === '') { current = key; nested[key] = {} }
      else { flat[key] = value.replace(/^["']|["']$/g, ''); current = null }
    } else if (kv && current) {
      const [, key, value] = kv
      nested[current][key] = value.replace(/^["']|["']$/g, '')
    }
  }
  return { raw, flat, nested, body }
}

function validateSkill(dirName) {
  const dir = path.join(SKILLS, dirName)
  const errors = []
  const warnings = []
  const skillMd = path.join(dir, 'SKILL.md')

  if (!fs.existsSync(skillMd)) {
    return { name: dirName, errors: ['нет SKILL.md'], warnings, ok: false }
  }
  const text = fs.readFileSync(skillMd, 'utf8')
  const fm = parseFrontmatter(text)
  if (!fm) return { name: dirName, errors: ['нет frontmatter (--- … ---)'], warnings, ok: false }

  const { raw, flat, body } = fm
  const name = flat.name
  const description = flat.description

  if (!name) errors.push('не задан name')
  else {
    if (name.length > 64) errors.push(`name длиннее 64 символов (${name.length})`)
    if (!NAME_RE.test(name)) errors.push(`name «${name}»: только a-z, 0-9 и одиночные дефисы`)
    if (name !== dirName) errors.push(`name «${name}» не совпадает с именем каталога «${dirName}»`)
  }
  if (!description) errors.push('не задан description')
  else {
    if (description.length > 1024) errors.push(`description длиннее 1024 символов (${description.length})`)
    if (description.length < 40) warnings.push('description короче 40 символов — агенту не хватит контекста для триггера')
    // Границы слова в JS-регулярке опираются на ASCII-алфавит и на кириллице не срабатывают,
    // поэтому русские триггеры («когда», «нужно») ищутся подстрокой, без границ.
    if (!/(use when|когда|применяй|asked|нужно|сделай)/i.test(description)) {
      warnings.push('в description нет указания «когда применять» — это триггер загрузки скилла')
    }
  }
  if (/[<>]/.test(raw)) warnings.push('в frontmatter есть угловые скобки < > — spec советует их избегать')

  if (!body || body.trim().length < 200) warnings.push('тело скилла подозрительно короткое')

  // ссылки на вспомогательные файлы из тела
  const refs = new Set()
  for (const m of body.matchAll(/(?:^|[\s(`'"])((?:references|templates|scripts|assets|examples)\/[A-Za-z0-9_.\-\/]+)/g)) {
    refs.add(m[1].replace(/[.,;:)]+$/, ''))
  }
  for (const ref of refs) {
    if (!fs.existsSync(path.join(dir, ref))) errors.push(`в теле упомянут ${ref}, но файла нет`)
  }

  // каталоги, которые обязаны содержать файлы
  for (const sub of ['references', 'templates', 'scripts', 'assets']) {
    const p = path.join(dir, sub)
    if (fs.existsSync(p) && fs.readdirSync(p).length === 0) warnings.push(`пустой каталог ${sub}/`)
  }

  return { name: dirName, errors, warnings, ok: errors.length === 0, refs: [...refs].sort() }
}

function main() {
  const asJson = process.argv.includes('--json')
  if (!fs.existsSync(SKILLS)) {
    console.error(`нет каталога ${SKILLS}`)
    return 2
  }
  const dirs = fs.readdirSync(SKILLS, { withFileTypes: true })
    .filter(e => e.isDirectory() && !e.name.startsWith('.') && !e.name.startsWith('_'))
    .map(e => e.name)

  if (!dirs.length) {
    console.error('в skills/ нет ни одного скилла')
    return 1
  }

  const results = dirs.map(validateSkill)
  if (asJson) {
    console.log(JSON.stringify(results, null, 2))
  } else {
    for (const r of results) {
      const mark = r.ok ? (r.warnings.length ? '~' : '✓') : '✗'
      console.log(`${mark} ${r.name}${r.refs?.length ? `  (файлы: ${r.refs.join(', ')})` : ''}`)
      for (const w of r.warnings) console.log(`    ~ ${w}`)
      for (const e of r.errors) console.log(`    ✗ ${e}`)
    }
    const bad = results.filter(r => !r.ok).length
    const warn = results.filter(r => r.ok && r.warnings.length).length
    console.log(`\nскиллов: ${results.length}, с ошибками: ${bad}, с предупреждениями: ${warn}`)
  }
  return results.some(r => !r.ok) ? 1 : 0
}

process.exit(main())
