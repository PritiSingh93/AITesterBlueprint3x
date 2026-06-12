const fs = require('fs')
const { marked } = require('marked')

const sample = fs.readFileSync('./sample.md', 'utf8')
let processed = sample.replace(/\{\{(https?:\/\/[^}]+)\}\}/g, '[$1]($1)')

// Steps block handling (copy of client logic)
const lines = processed.split(/\r?\n/)
let stepsIndex = -1
for (let i = 0; i < lines.length; i++) {
  if (/steps to reproduce/i.test(lines[i])) { stepsIndex = i; break }
}
console.log('stepsIndex=', stepsIndex)
console.log('context around stepsIndex:')
for (let k = Math.max(0, stepsIndex-2); k <= Math.min(lines.length-1, stepsIndex+5); k++) {
  console.log(k, JSON.stringify(lines[k]))
}
if (stepsIndex >= 0) {
  const items = []
  let i = stepsIndex + 1
  for (; i < lines.length; i++) {
    const rawLine = lines[i]
    const line = rawLine.trim()
    console.log('line', i, JSON.stringify(line))
    // skip blank lines between header and the first step
    if (!line) { console.log('  skip blank'); continue }
    // normalize leading markdown markers for reliable section-name detection
    const norm = line.replace(/^[>\s*_#-]+/, '').trim()
    // stop if we hit an obvious next section header by name (not generic markdown headings)
    if (/^(Expected Result|Actual Result|Environment|Acceptance Criteria|Scope|Strategy|Entry Criteria|Exit Criteria|Risks|Assumptions|Dependencies|Traceability|Sign-off)\b/i.test(norm)) { console.log('  stop at next section'); break }
    // treat headings like '## Navigate to...' as step lines too — strip leading hashes, bullets or numbers but preserve emphasis markers inside text
    const step = line.replace(/^\s*(?:#+\s+|\d+\.\s+|[-*]\s+)/, '').trim()
    console.log('  step=', JSON.stringify(step))
    if (step) items.push(step)
  }
  console.log('collected items:', items)
  if (items.length) {
    const listHtml = '<div class="tp-steps">' + items.map((s, idx) => {
      const htmlText = marked.parseInline(s)
      return `<div class="tp-step"><span class="tp-step-num">${idx+1}</span><div class="tp-step-text">${htmlText}</div></div>`
    }).join('') + '</div>'
    const before = lines.slice(0, stepsIndex + 1).join('\n')
    const after = lines.slice(i).join('\n')
    processed = before + '\n\n' + listHtml + '\n\n' + after
  }
} else {
  processed = processed.replace(/(^|\n)\*\s+/g, '$1- ')
}
processed = processed.replace(/\n{3,}/g, '\n\n')

// heading renderer
const renderer = {
  heading(text, level, raw, slugger) {
    const tag = level === 1 ? 'h2' : level === 2 ? 'h3' : level === 3 ? 'h4' : 'h5'
    return `<${tag}>${text}</${tag}>\n`
  }
}
marked.use({ renderer })
const html = marked.parse(processed)
console.log('---- PROCESSED TEXT ----')
console.log(processed)
console.log('\n---- RENDERED HTML ----')
console.log(html)
