// Report breaking changes between two versions of an AsyncAPI contract.
// Usage: node asyncapi-breaking.mjs <old.yaml> <new.yaml>
// Exit code 1 when a breaking change is found, 2 when a document cannot be parsed.
//
// Two checks:
// 1. Structure (channels, operations, servers): @asyncapi/diff.
// 2. Message payloads: the adidas "rules for extending". @asyncapi/diff leaves payload schema
//    changes unclassified, so they are checked here:
//    - MUST NOT take anything away: removed messages, properties or enum values are breaking.
//    - MUST NOT make optional things required / anything added MUST be optional: any change to
//      `required` is breaking, so a new property must be optional.
//    - MUST NOT change processing rules: changed types, constants or constraints are breaking.
//    Adding optional properties, adding enum values (consumers are tolerant readers) and
//    changing descriptions or examples are not breaking.

import { resolve } from 'node:path';
import { Parser, fromFile } from '@asyncapi/parser';
import diffPackage from '@asyncapi/diff';

const { diff } = diffPackage;
const CONSTRAINTS = [
  'type', 'const', 'format', 'pattern', 'minLength', 'maxLength', 'minimum', 'maximum',
  'exclusiveMinimum', 'exclusiveMaximum', 'minItems', 'maxItems', 'uniqueItems',
  'additionalProperties', 'multipleOf',
];

const parser = new Parser();

async function parse(path) {
  const { document, diagnostics } = await fromFile(parser, resolve(path)).parse();
  if (!document) {
    const errors = diagnostics
      .filter((d) => d.severity === 0)
      .map((d) => `${d.path.join('.')}: ${d.message}`);
    console.error(`Cannot parse ${path}:\n  ${errors.join('\n  ')}`);
    process.exit(2);
  }
  return document.json();
}

function messagesOf(document) {
  const messages = new Map();
  for (const [channel, item] of Object.entries(document.channels ?? {})) {
    for (const operation of ['publish', 'subscribe']) {
      const message = item[operation]?.message;
      for (const one of message?.oneOf ?? (message ? [message] : [])) {
        messages.set(`${channel} ${operation} ${one.messageId ?? one.name}`, one.payload ?? {});
      }
    }
  }
  return messages;
}

function compareSchemas(before, after, path, problems) {
  if (typeof before !== 'object' || before === null || typeof after !== 'object' || after === null) {
    if (JSON.stringify(before) !== JSON.stringify(after)) problems.push(`${path}: changed`);
    return;
  }
  for (const keyword of CONSTRAINTS) {
    if (JSON.stringify(before[keyword]) !== JSON.stringify(after[keyword])) {
      problems.push(`${path}: ${keyword} changed from ${JSON.stringify(before[keyword])} to ${JSON.stringify(after[keyword])}`);
    }
  }
  const requiredBefore = [...(before.required ?? [])].sort();
  const requiredAfter = [...(after.required ?? [])].sort();
  if (JSON.stringify(requiredBefore) !== JSON.stringify(requiredAfter)) {
    problems.push(`${path}: required changed from [${requiredBefore}] to [${requiredAfter}]`);
  }
  for (const value of before.enum ?? []) {
    if (!(after.enum ?? []).some((v) => JSON.stringify(v) === JSON.stringify(value))) {
      problems.push(`${path}: enum value ${JSON.stringify(value)} removed`);
    }
  }
  for (const [name, schema] of Object.entries(before.properties ?? {})) {
    if (!(name in (after.properties ?? {}))) problems.push(`${path}.${name}: property removed`);
    else compareSchemas(schema, after.properties[name], `${path}.${name}`, problems);
  }
  if (before.items || after.items) compareSchemas(before.items, after.items, `${path}[]`, problems);
  for (const combinator of ['allOf', 'anyOf', 'oneOf']) {
    const left = before[combinator] ?? [];
    const right = after[combinator] ?? [];
    if (left.length !== right.length) problems.push(`${path}: ${combinator} changed`);
    else left.forEach((schema, i) => compareSchemas(schema, right[i], `${path}.${combinator}[${i}]`, problems));
  }
}

const [oldPath, newPath] = process.argv.slice(2);
if (!oldPath || !newPath) {
  console.error('Usage: node asyncapi-breaking.mjs <old.yaml> <new.yaml>');
  process.exit(2);
}
const [before, after] = [await parse(oldPath), await parse(newPath)];

// Raising info.version is required on every change (checked by contract_check.py), not breaking.
const OVERRIDE = {
  '/info/version': { add: 'non-breaking', remove: 'breaking', edit: 'non-breaking' },
};
const problems = diff(before, after, { override: OVERRIDE })
  .breaking()
  .map((c) => `structure: ${c.action} ${c.path}`);
const [messagesBefore, messagesAfter] = [messagesOf(before), messagesOf(after)];
for (const [key, payload] of messagesBefore) {
  if (!messagesAfter.has(key)) problems.push(`${key}: message removed`);
  else compareSchemas(payload, messagesAfter.get(key), `${key} payload`, problems);
}

for (const problem of problems) console.log(`BREAKING ${problem}`);
if (problems.length === 0) console.log('No breaking changes.');
process.exit(problems.length > 0 ? 1 : 0);
