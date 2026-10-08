import { z } from 'zod'

// The server (bcrypt) takes at most 72 bytes and answers longer passwords with 422.
// Count bytes, not characters: a Cyrillic letter takes two bytes in UTF-8.
export const PASSWORD_MIN_CHARS = 8
export const PASSWORD_MAX_BYTES = 72

// The server counts code points (pydantic), not UTF-16 units: an emoji is one character here, two in JS .length.
export const passwordRule = z.string()
  .refine(p => [...p].length >= PASSWORD_MIN_CHARS, `Минимум ${PASSWORD_MIN_CHARS} символов`)
  .refine(p => new TextEncoder().encode(p).length <= PASSWORD_MAX_BYTES,
    `Не больше ${PASSWORD_MAX_BYTES} байт: кириллица занимает два байта на букву`)
