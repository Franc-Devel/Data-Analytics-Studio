const test = require('node:test');
const assert = require('node:assert');
const crypto = require('crypto');
const { safeCompareTokens } = require('../server');

test('WhatsApp Bridge - safeCompareTokens timing-safe comparison', () => {
  const secret = 'SecretToken#2026_XYZ';
  
  // Valid token
  assert.strictEqual(safeCompareTokens(secret, secret), true);
  
  // Invalid tokens
  assert.strictEqual(safeCompareTokens('WrongToken', secret), false);
  assert.strictEqual(safeCompareTokens('', secret), false);
  assert.strictEqual(safeCompareTokens(null, secret), false);
  assert.strictEqual(safeCompareTokens(undefined, secret), false);
  assert.strictEqual(safeCompareTokens(secret + 'extra', secret), false);
});

test('WhatsApp Bridge - Payload validation format', () => {
  const cleanPhone = (phone) => String(phone).replace(/\D/g, '');
  
  assert.strictEqual(cleanPhone('+54 9 11 2345-6789'), '5491123456789');
  assert.strictEqual(cleanPhone('5491123456789'), '5491123456789');
  assert.strictEqual(cleanPhone('').length < 8, true);
});
