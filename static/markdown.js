/**
 * Render the Markdown subset the agent emits: paragraphs, headings, bullet
 * and numbered lists, tables, bold, italic and code.
 *
 * Nodes are built with the DOM API and text is only ever assigned through
 * textContent, so a reply can never be interpreted as HTML. That matters
 * here because answers quote figures and names from data files, and the
 * agent is explicitly allowed to repeat text from uploaded documents when
 * reporting a prompt-injection attempt.
 */

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g;

function inline(text, parent) {
  for (const part of text.split(INLINE)) {
    if (!part) continue;
    if (part.startsWith("**") && part.endsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = part.slice(2, -2);
      parent.appendChild(strong);
    } else if (part.startsWith("`") && part.endsWith("`")) {
      const code = document.createElement("code");
      code.textContent = part.slice(1, -1);
      parent.appendChild(code);
    } else if (part.startsWith("*") && part.endsWith("*")) {
      const em = document.createElement("em");
      em.textContent = part.slice(1, -1);
      parent.appendChild(em);
    } else {
      parent.appendChild(document.createTextNode(part));
    }
  }
}

const BULLET = /^\s*[-*+]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^(#{1,6})\s+(.*)$/;

/** A row of "---" or ":--" cells, which is what marks the line above as a header. */
function isTableRule(line) {
  return /\|/.test(line) && /^[\s|:-]+$/.test(line) && line.includes("-");
}

function splitRow(line) {
  return line.trim().replace(/^\||\|$/g, "").split("|").map((cell) => cell.trim());
}

function buildTable(lines, start) {
  const header = splitRow(lines[start]);
  const table = document.createElement("table");

  const headRow = table.createTHead().insertRow();
  for (const cell of header) {
    const th = document.createElement("th");
    inline(cell, th);
    headRow.appendChild(th);
  }

  const body = table.createTBody();
  let i = start + 2;
  for (; i < lines.length && lines[i].includes("|"); i++) {
    const row = body.insertRow();
    for (const cell of splitRow(lines[i])) {
      // Right-align anything that reads as a number, so columns line up.
      const td = row.insertCell();
      if (/^[-+$]?[\d,.]+%?$/.test(cell)) td.className = "num";
      inline(cell, td);
    }
  }
  return [table, i];
}

function buildList(lines, start, pattern, tag) {
  const list = document.createElement(tag);
  let i = start;
  for (; i < lines.length; i++) {
    const match = lines[i].match(pattern);
    if (!match) break;
    const item = document.createElement("li");
    inline(match[1], item);
    list.appendChild(item);
  }
  return [list, i];
}

export function renderMarkdown(text) {
  const fragment = document.createDocumentFragment();
  const lines = String(text).split("\n");

  for (let i = 0; i < lines.length; ) {
    const line = lines[i];

    if (!line.trim()) {
      i++;
      continue;
    }

    if (line.includes("|") && isTableRule(lines[i + 1] || "")) {
      const [table, next] = buildTable(lines, i);
      fragment.appendChild(table);
      i = next;
      continue;
    }

    const heading = line.match(HEADING);
    if (heading) {
      // Headings are capped at h3: these sit inside a chat bubble, not a page.
      const el = document.createElement(`h${Math.min(heading[1].length + 2, 6)}`);
      inline(heading[2], el);
      fragment.appendChild(el);
      i++;
      continue;
    }

    if (BULLET.test(line)) {
      const [list, next] = buildList(lines, i, BULLET, "ul");
      fragment.appendChild(list);
      i = next;
      continue;
    }

    if (NUMBERED.test(line)) {
      const [list, next] = buildList(lines, i, NUMBERED, "ol");
      fragment.appendChild(list);
      i = next;
      continue;
    }

    // Everything else is a paragraph, running until a blank line or a block.
    const paragraph = document.createElement("p");
    let first = true;
    for (; i < lines.length; i++) {
      const current = lines[i];
      if (!current.trim() || BULLET.test(current) || NUMBERED.test(current) ||
          HEADING.test(current) || isTableRule(lines[i + 1] || "")) {
        break;
      }
      if (!first) paragraph.appendChild(document.createElement("br"));
      inline(current, paragraph);
      first = false;
    }
    fragment.appendChild(paragraph);
  }

  return fragment;
}
