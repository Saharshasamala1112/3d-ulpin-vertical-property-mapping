# Vertical DNA Code (VDC) Specification

- **Document:** VDC Specification (this document)
- **Specification version:** 1.0
- **Date:** 2026-09-20
- **Status:** Draft — pending technical review
- **Purpose:** Define — precisely and unambiguously — the Vertical DNA Code (VDC): a single ASCII string that encodes a Unique Land Parcel Identification Number (ULPIN), a property domain code, a vertical level (floor or basement), a unit identifier, and a checksum. The specification exists so that a parser, a validator, a generator, and a checksum verifier can be implemented independently by different developers and still agree on every legal and illegal value.
- **Scope:** This document covers only the syntax, structure, character sets, length constraints, canonicalization rules, and checksum algorithm of the VDC. It does not specify software, algorithms for data storage, government data systems, or any implementation.
- **Standards alignment note:** This specification is a **project-level engineering convention (GEOSIX VDC)**. It is authored by no government body, is not endorsed or mandated by any government program, and does not implement, modify, or reference any official ULPIN or government data standard. Any ULPIN values shown are GEOSIX example values, not real issued ULPINs.

---

## 1. Terminology

| Term    | Meaning |
|---------|------------------------------|
| **ULPIN** | Unique Land Parcel Identification Number. In this specification, the GEOSIX representation of a land parcel identifier, used as the first segment of a VDC. |
| **VDC** | Vertical DNA Code. The complete ASCII string defined by this specification, composed of five hyphen-separated segments (ULPIN, DOMAIN, LEVEL, UNIT, CHECKSUM). |
| **DOMAIN** | The property domain segment: a single uppercase letter classifying the type of property. |
| **LEVEL** | The vertical-level segment: the floor or basement designator (e.g., ground, floor 5, basement 2). |
| **UNIT** | The unit segment: the identifier of a unit/apartment within the property (e.g., "1", "804", "25B", "1234AB"). |
| **CHECKSUM** | A two-character segment computed from the first four segments by the algorithm defined in section 9; used to detect transcription errors. |
| **separator** | The literal ASCII hyphen character `-` (U+002D). It is the only separator permitted in a VDC. |
| **segment** | One of the five hyphen-delimited parts of a VDC. |
| **canonical form** | The single, unambiguous, normalized representation of a VDC (see section 10). |
| **GEOSIX VDC** | The project-level encoding convention defined in this document; also the `DOMAIN` code set. |
| **ULPIN representation** | The way a ULPIN appears within a VDC: exactly 10 ASCII uppercase alphanumeric characters, the first of which is an uppercase letter (see section 5). |

---

## 2. VDC format overview

A VDC is a single string, with no embedded spaces or other whitespace, consisting of five segments separated by exactly one literal hyphen between consecutive segments:

```
ULPIN-DOMAIN-LEVEL-UNIT-CHECKSUM
```

- The separator is always the ASCII hyphen `-` (`0x2D`).
- No whitespace of any kind (space, tab, newline, CR) is permitted, neither inside a segment nor as a separator substitute. A VDC is exactly one line of text.
- All letters are uppercase ASCII `A`–`Z`; lowercase letters are not valid in a VDC and MUST be rejected during validation (see section 10).
- The four leading segments establish an unambiguous canonical form; the CHECKSUM is derived from the concatenation of those four segments.

The complete canonical form has exactly 4 hyphens gluing 5 segments. The general shape is:

```
<ULPIN(10)>-<DOMAIN(1)>-<LEVEL(1..4)>-<UNIT(1..6)>-<CHECKSUM(2)>
```

where the numbers in parentheses are the character-length ranges (lengths of the corresponding segments, hyphen not counted). The total VDC length is therefore 19 to 27 characters (inclusive); outliers are invalid.

### 2.1 Canonical representation rules

1. **Precisely one** canonical string exists for every valid VDC.
2. The canonical form uses ASCII uppercase letters and digits only.
3. Hyphens appear exactly 4 times, at fixed positions:
   - after the 10th character (ULPIN boundary),
   - after the 11th character (DOMAIN boundary),
   - after the LEVEL segment,
   - after the UNIT segment.
   No hyphen is ever allowed inside any segment.
4. The canonical form is the form that a generator MUST emit, a validator MUST require, and a canonicalizer MUST map to.
5. VDC strings are equal if and only if their canonical strings are identical; lowercase input is invalid and MUST be rejected (see section 10).

---

## 3. Formal grammar

The following grammar is ABNF-compatible (RFC 5234) with one explicit clarification: the two-digit base-36 encoding is expressed inline. This grammar is **unambiguous**: for any valid input string, the segmentation into the five segments is unique.

```abnf
vdc           = ulpin "-" domain "-" level "-" unit "-" checksum

ulpin         = "GEOSX" 5DIGIT      ; project lead-in (GEOSIX ULPIN head); exactly 10 chars: 5-letter head + 5-digit serial
              ; exactly 10 chars; first char is an uppercase letter

domain        = %x41-44              ; 'A' 'B' 'C' 'D' — GEOSIX VDC domain code

level         = ground / raised / basement
ground        = "G"
raised        = "F" positive-int     ; 'F' plus a positive integer w/o leading zero
basement      = "B" positive-int     ; 'B' plus a positive integer w/o leading zero

positive-int  = nonzero *2DIGIT      ; 1 to 3 digits, no leading zeros

unit          = (ALPHA / nonzero) *(ALPHA / DIGIT)
              ; 1 to 6 chars; first char is letter or non-zero digit;
              ; subsequent chars are letters or digits; no leading zero

checksum      = base36 base36        ; two chars, as defined in section 9

ALPHA         = %x41-5A              ; 'A'-'Z' (uppercase only)
DIGIT         = %x30-39              ; '0'-'9'
ALNUM         = ALPHA / DIGIT
nonzero       = %x31-39              ; '1'-'9'
base36        = DIGIT / ALPHA        ; the 36 chars used by the checksum
```

Notes on the grammar:

- `positive-int` allows 1 to 3 digits with no leading zeros (values `1`..`999`). This bounds LEVEL length to at most 4 characters (`F999`, `B999`).
- `unit` allows 1 to 6 characters. Its first character must be a letter (`A`–`Z`) or a non-zero digit (`1`–`9`); therefore a unit never has a leading zero base-10 value when it begins with digits.
- `ALPHA` is uppercase-only: lowercase letters are not part of the VDC alphabet.

The grammar is unambiguous because ULPIN and DOMAIN have fixed lengths and
the ASCII hyphens explicitly delimit the five segments. LEVEL and UNIT are
validated independently against their respective productions.

---

## 4. Character sets and length constraints

| Segment  | Character set (ASCII)                                                     | Length (chars) | Length kind |
|----------|---------------------------------------------------------------------------|----------------|-------------|
| ULPIN    | `A`–`Z` (first char forced letter), then `A`–`Z` / `0`–`9`                | exactly 10     | fixed       |
| DOMAIN   | `A`–`D` (GEOSIX VDC codes, see section 6)                                 | exactly 1      | fixed       |
| LEVEL    | `G` or (`F` / `B` + `1`–`3` digits, first digit `1`–`9`, no leading zeros) | 1 to 4         | variable     |
| UNIT     | `A`–`Z` / `0`–`9`; first char letter or `1`–`9` (no leading zero)          | 1 to 6         | variable     |
| CHECKSUM | `0`–`9` / `A`–`Z` (base-36)                                                | exactly 2      | fixed       |

- **Fixed-length segments:** ULPIN (10), DOMAIN (1), CHECKSUM (2).
- **Variable-length segments:** LEVEL (1–4), UNIT (1–6).
- **Total length:** 19–27 characters as stated in section 2.
- **Leading zeros:** prohibited in every numeric position where a canonical base-10 value is meaningful (LEVEL digits, UNIT leading digit). The ULPIN carries its zeros as part of its fixed 10-character code (see section 6) and is not subject to this rule; likewise the CHECKSUM may legitimately contain `0` characters as checksum digits (they are not leading zeros, they are checksum values).
- **Invalid characters:** anything outside the sets above (lowercase letters, punctuation other than the 4 hyphens, underscores, spaces) is invalid.

---

## 5. ULPIN segment

Within a VDC, the ULPIN is represented as exactly **10 ASCII characters**:

- characters 0 (the first) is one of `A`–`Z`;
- characters 1–9 are each one of `A`–`Z` or `0`–`9`.

The fixed GEOSIX ULPIN head is `GEOSX` (5 characters) followed by a 5-digit numeric serial (matches the fixed 10-char scheme).

This specification does **not** claim any government-mandated ULPIN format for the head `GEOSX`. The head `GEOSX` is the **GEOSIX VDC project-level ULPIN representation** — a self-chosen engineering convention, explained to avoid confusing the reader with any official government identity. Any string in this document beginning with `GEOSX` is an example, not a real issued parcel number.

---

## 6. DOMAIN segment

The DOMAIN segment is one letter from the GEOSIX VDC domain code set. The mapping below is a **project-level convention (GEOSIX VDC)** and is NOT an official government code set.

| Code | Domain                          |
|------|---------------------------------|
| A    | Residential                     |
| B    | Commercial                      |
| C    | Industrial                      |
| D    | Civic / Institutional           |

Unknown letters (`E`–`Z`) and any other character are invalid; a future revision may extend this table.

---

## 7. LEVEL segment

LEVEL uses a three-rule encoding:

| Rule                    | Code  | Value |
|-------------------------|-------|-------|
| Ground level            | `G`   | ground |
| Positive floor f        | `F` + `f` | floor number, no leading zeros |
| Basement level b (1 = first basement) | `B` + `b` | below-ground level, no leading zeros |

### 7.1 Exact encoding rules

1. **Ground level** is the single letter `G`.
2. **Positive floors:** the letter `F` followed immediately by the decimal floor number with **no leading zeros**. A floor number is 1 to 3 digits (integer `1`..`999`). Examples: `F1`, `F5`, `F9`, `F12`, `F120`, `F999`.
3. **Basements:** the letter `B` followed immediately by the decimal depth with **no leading zeros**. First basement = `B1`, second = `B2`, ..., up to `B999`. Examples: `B1`, `B2`, `B3`, `B9`, `B12`, `B120`.
4. There is no `B` alone (no "basement zero"); the ground level is always `G`. A basement deeper than `B999` cannot be represented in this version.
5. Look-alike `F`/`B` are unambiguous because `F` always precedes a raised floor number and `B` always precedes a basement depth.
6. No zero digit may precede any digit in a numeric `LEVEL`: `F01`, `F05`, `B03` are all invalid.

### 7.2 Length summary

| Encoding | Length | Example |
|----------|--------|---------|
| `G`                        | 1 | `G` |
| Positive floor (1–3 digits) | 2–4 | `F1`, `F12`, `F120`, `F999` |
| Basement (1–3 digits)       | 2–4 | `B1`, `B9`, `B120` |

---

## 8. UNIT segment

UNIT is the identifier for a unit/apartment/office within a parcel.

### 8.1 Exact encoding rules

1. **Length:** 1 to 6 characters.
2. **Character set:** uppercase `A`–`Z` and digits `0`–`9`.
3. **First character:** a letter (`A`–`Z`) or a non-zero digit (`1`–`9`). This guarantees a unit has no leading zero when it is numeric, and makes units like `1`, `12`, `804`, `25B`, `9A`, `1234AB` all legal.
4. **Subsequent characters:** any of `A`–`Z` / `0`–`9`.
5. **Leading zeros disabled:** `01`, `0`, `007` are invalid because the first character is `0`. A multi-digit numeric unit is written without leading zeros: `1`, `12`, `1001`, not `0001`.
6. A unit may be purely numeric (`1`, `804`, `1001`), purely alphabetic (`B`, `AB`), or mixed (`25B`, `9A`, `1234AA`); lowercase is invalid (`1234aa`, `25b` MUST be rejected, not folded).
7. If a unit begins with a letter, it may contain digits; if it begins with a digit, it may contain letters. Any mix of `A`–`Z` and `0`–`9` is allowed after the first character.

### 8.2 Examples of legal/illegal UNIT values

| UNIT    | Legal? | Reason |
|---------|--------|--------|
| `1`     | yes    | single-digit unit |
| `804`   | yes    | multi-digit unit |
| `1001`  | yes    | multi-digit unit (4 digits) |
| `25B`   | yes    | alphanumeric, letter-terminated |
| `9A`    | yes    | letter after digit |
| `1234AB`| yes    | 6-char alphanumeric |
| `AB12`  | yes    | leading letters |
| `01`    | no     | leading zero |
| `0`     | no     | leading zero (and reserved: see below) |
| `1234ABC`| no    | length exceeds 6 |
| `25-B`  | no     | hyphen not allowed inside segment |

The UNIT value `0` alone is **reserved and invalid**; the ground-level, single-unit convention is `UNIT=1` (see worked examples). SECTION 10 rejects any leading-zero form.

---

## 9. CHECKSUM

The CHECKSUM is 2 characters generated deterministically from the first four canonical segments. **The checksum is NOT reversible in the information-theoretic sense:** given only the 2 checksum characters you cannot reconstruct the ULPIN/DOMAIN/LEVEL/UNIT. What this specification provides is:

- **Deterministic generation:** the same 4 segments always produce the same 2 checksum characters;
- **Checksum verification:** a validator recomputes the checksum from the 4 segments and compares it to the supplied checksum — if they differ, the VDC is invalid;
- **Reversible / unambiguous parsing:** the VDC *segments* themselves (sections 2–8) are fully reversible — you can parse the canonical string back into ULPIN, DOMAIN, LEVEL, UNIT without loss. Reversibility applies to parsing the segments, NOT to the checksum.

The checksum therefore detects transcription errors, not forgery or malicious modification; it is not a cryptographic hash and must not be treated as one (see section 15).

### 9.1 Charset and value table

The checksum uses the base-36 alphabet:

```
Index: 0   1   2   3   4   5   6   7   8   9   10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31  32  33  34  35
Char : 0   1   2   3   4   5   6   7   8   9   A   B   C   D   E   F   G   H   I   J   K   L   M   N   O   P   Q   R   S   T   U   V   W   X   Y   Z
```

The value of a character is its index in this table (`0`=`0`, ..., `9`=`9`, `A`=`10`, ..., `Z`=`35`).

### 9.2 Input canonicalization for the checksum

Checksum input is the concatenation of the four canonical segments, in order, WITHOUT separators:

```
input = ULPIN + DOMAIN + LEVEL + UNIT
```

To make the input to the checksum deterministic, sections 2–8 define a
canonical encoding. This concatenation is deterministic: given the same set
of canonical segments, the same input string is always produced. The
concatenated checksum input is an internal representation only — it is
**never** parsed back into segments, and a consumer MUST NOT attempt to
re-split it. It carries no hyphens, no whitespace, and no lowercasing: the
checksum is computed over the canonical uppercase string exactly as it
appears.

No hyphens, no whitespace, no lowercasing: the checksum is computed over the canonical uppercase string exactly as it appears.

### 9.3 Checksum algorithm (pseudocode)

```
CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
VALUE[c] = index of c within CHARSET          // 0..35

function CHECKSUM(ULPIN, DOMAIN, LEVEL, UNIT) returns string(2):
    input  = ULPIN + DOMAIN + LEVEL + UNIT   // concatenation, no hyphen
    c1 = 0
    c2 = 0
    for i from 0 to length(input) - 1:
        v = VALUE[ input[i] ]
        c1 = (c1 + v) mod 36
        c2 = (c2 + ((i + 1) * v)) mod 36
    checksum = CHARSET[c1] + CHARSET[c2]
    return checksum
```

Example verified above: for `ULPIN=GEOSX00001, DOMAIN=A, LEVEL=G, UNIT=1`:

```
input = GEOSX00001 + A + G + 1  =  GEOSX00001AG1
values: G=16 E=14 O=24 S=28 X=33 0=0 0=0 0=0 0=0 1=1 A=10 G=16 1=1
c1 = (16+14+24+28+33+0+0+0+0+1+10+16+1) mod 36 = 143 mod 36 = 35 → 'Z'
c2 = (1*16 + 2*14 + 3*24 + 4*28 + 5*33 + 6*0 + 7*0 + 8*0 + 9*0
      + 10*1 + 11*10 + 12*16 + 13*1) mod 36
   = 718 mod 36 = 34 → 'Y'
CHECKSUM = "ZY"
```

Verification procedure: recompute `CHECKSUM(ULPIN, DOMAIN, LEVEL, UNIT)`. If it equals the supplied checksum string, the VDC is valid against the checksum; otherwise it is invalid. The verification is a strict equality of the two-character string.

---

## 10. Canonicalization and validation rules

### 10.1 Canonicalization (from any well-formed uppercase VDC)

Given an input VDC string (may be a non-canonical but structurally valid uppercase variant):

1. Split on the four hyphens into exactly 5 segments. If the split does not yield exactly 5 segments, the value is invalid (missing/extra hyphen).
2. Require uppercase ASCII characters; lowercase characters are invalid and MUST be rejected. No implicit uppercasing is performed.
3. Strip outer whitespace only if it appears at the very beginning/end of the whole string (never inside segments), then treat the canonical string as trimmed.
4. Reject any string still containing internal spaces.
5. Reject any segment that does not match its grammar (section 3).

### 10.2 Validation rules (summary)

| Concern                | Rule |
|------------------------|------|
| Case                   | Uppercase ASCII only; lowercase characters are invalid and MUST be rejected. |
| Whitespace             | None permitted anywhere within a VDC (including inside segments). Leading/trailing whitespace of the entire string may be trimmed by a pre-parser before validation. |
| Separators             | Exactly 4 hyphens, each between segments; no hyphen inside a segment; no empty segment. |
| Leading zeros          | Prohibited in LEVEL numeric value and UNIT leading position (see sections 7, 8). |
| Checksum input         | Concatenation ULPIN+DOMAIN+LEVEL+UNIT (no separators), computed on canonical uppercase segments. |
| Invalid forms          | Lowercase letters, extra/missing hyphens, empty segments, whitespace, out-of-range lengths, unknown DOMAIN or LEVEL codes, checksum mismatch. |
| Canonical output       | `ULPIN-DOMAIN-LEVEL-UNIT-CHECKSUM`, uppercase, exactly the 5 segments, no trailing newline, LF-only line ending if serialized to a file. |

---

## 11. Worked examples

All checksums below were computed with the reference algorithm (section 9). ULPINs are GEOSIX example values starting `GEOSX00001`..`GEOSX00012`; these are illustrative and not real issued parcels.

| # | ULPIN      | DOMAIN | LEVEL | UNIT  | CHECKSUM | Complete VDC |
|---|------------|--------|-------|-------|----------|------------------------------|
| 1 | GEOSX00001 | A      | G     | 1     | ZY       | GEOSX00001-A-G-1-ZY |
| 2 | GEOSX00002 | A      | F5    | 3     | 6I       | GEOSX00002-A-F5-3-6I |
| 3 | GEOSX00003 | A      | F12   | 804   | E6       | GEOSX00003-A-F12-804-E6 |
| 4 | GEOSX00004 | A      | B1    | 4     | 1O       | GEOSX00004-A-B1-4-1O |
| 5 | GEOSX00005 | A      | B3    | 7     | 7U       | GEOSX00005-A-B3-7-7U |
| 6 | GEOSX00006 | B      | G     | 105   | AQ       | GEOSX00006-B-G-105-AQ |
| 7 | GEOSX00007 | C      | F120  | 25B   | QF       | GEOSX00007-C-F120-25B-QF |
| 8 | GEOSX00008 | A      | G     | 1001  | 7C       | GEOSX00008-A-G-1001-7C |
| 9 | GEOSX00009 | B      | B2    | 9A    | NU       | GEOSX00009-B-B2-9A-NU |
| 10| GEOSX00010 | A      | F9    | 5     | BF       | GEOSX00010-A-F9-5-BF |
| 11| GEOSX00011 | A      | F999  | 1234AB| KZ      | GEOSX00011-A-F999-1234AB-KZ |
| 12| GEOSX00012 | D      | B9    | 3     | AS       | GEOSX00012-D-B9-3-AS |

Coverage of required example classes:

- **Ground level:** #1 (`G`), and see #6 (#all units).
- **Single-digit positive floor:** #2 (`F5`), #10 (`F9`).
- **Multi-digit positive floor:** #3 (`F12`), #7 (`F120`), #11 (`F999`).
- **First basement:** #4 (`B1`).
- **Multiple basement levels:** #5 (`B3`), #9 (`B2`), #12 (`B9`).
- **Single-digit unit:** #1 (`1`), #2 (`3`), #4 (`4`), #5 (`7`), #10 (`5`), #12 (`3`).
- **Multi-digit unit:** #3 (`804`), #6 (`105`), #8 (`1001`).
- **Different domain code:** #6 (`B`), #7 (`C`), #9 (`B`), #12 (`D`).
- **Edge cases:** #7 (alphanumeric unit `25B`, 3-digit floor `F120`), #9 (alphanumeric unit `9A`, basement), #11 (max floor `F999`, 6-char unit `1234AB`), #12 (deep basement `B9`, different domain `D`).

### 11.1 Worked example #1 (full derivation)

```
VDC       : GEOSX00001-A-G-1-ZY
ULPIN     : GEOSX00001
DOMAIN    : A      (Residential)
LEVEL     : G      (ground)
UNIT      : 1
CHECKSUM  : ZY
```

Derivation (as in section 9.3): input string for the checksum is `GEOSX00001AG1`; `c1`=35 (`Z`), `c2`=34 (`Y`).

### 11.2 Worked example #7 (multi-skill case)

```
VDC       : GEOSX00007-C-F120-25B-QF
ULPIN     : GEOSX00007
DOMAIN    : C      (Industrial)
LEVEL     : F120   (120th floor)
UNIT      : 25B
CHECKSUM  : QF
```

This combines a 3-digit floor number, a multi-digit 3-char alphanumeric unit, and a non-residential domain — the maximum involved combination that is still within the allowed ranges.

### 11.3 Worked example #12 (deep basement, different domain)

```
VDC       : GEOSX00012-D-B9-3-AS
ULPIN     : GEOSX00012
DOMAIN    : D      (Civic / Institutional)
LEVEL     : B9     (9th basement)
UNIT      : 3
CHECKSUM  : AS
```

---

## 12. Edge cases

| Case | Behavior |
|------|----------|
| **Basement levels** | encoded `B1`, `B2`, ...; no `B` alone, no `B0`; `B999` is max. |
| **Single-digit floors** | `F1`..`F9`, one character `2` (e.g., `F5`). |
| **Multi-digit floors** | `F10`..`F999`; e.g., `F12`, `F120`. |
| **Single-digit units** | `1`..`9`, e.g., `3`, `7`. |
| **Multi-digit units** | `10`..`999999`-ish but bounded 6 chars, no leading zeros beyond the value; e.g., `804`, `1001`, `1234AB`. |
| **Leading zeros** | Prohibited: `F01`, `B03`, `UNIT 01` are invalid; the canonical forms are `F1`, `B3`, `UNIT 1`. The ULPIN's fixed `00000`..`99999` serial keeps leading zeros by design and is not affected. |
| **Invalid characters** | anything outside `A-Z0-9` (after removing exactly 4 hyphens) is invalid, as are lowercase letters. |
| **Malformed separators** | 0–3 or 5+ hyphens → invalid; `--` (double hyphen) → empty segment → invalid; leading/trailing hyphen → empty segment → invalid. |
| **Checksum mismatch** | recompute and compare (section 9); mismatch → invalid VDC. |
| **Ambiguous/non-canonical representations** | a unique canonical form exists for every valid VDC; any other spelling (e.g., `GEOSX00001-A-G-1` — missing checksum, or `GEOSX00001Ag1ZY` — missing hyphens) is invalid. `GEOSX00001-A-G-1-ZY` is the only valid form of that VDC. |
| **Checksum containing `0`** | allowed: `0` is a legitimate checksum character; it is not a leading zero because checksum is a fixed 2-char value, e.g. `...-1O` (example #4). |

---

## 13. Versioning

- This document is **VDC Specification version 1.0**.
- **Incompatible format changes** (any change to the syntax, encoding of segments, checksum algorithm, or canonicalization that could produce different valid/invalid sets or different checksums) increment the **major version** (e.g., 1.0 → 2.0). Implementations must reject VDCs whose spec version they do not understand.
- **Compatible changes** (clarifications, additional worked examples, editorial fixes, extending the DOMAIN table with additional entry that adds new valid values without removing any existing valid value, or documenting behavior already implied by the grammar) advance the **minor/patch** version (1.0 → 1.1) and do not break existing valid values.
- While version 1.0 is in Draft, incompatible refinements discovered during review bump the draft number (e.g., 1.0-draft-1 → 1.0-draft-2) and are resolved to 1.0 at approval.

---

## 14. Parsing and validation guidance (conceptual, documentation only)

This section describes the intended sequence a future implementer SHOULD follow. It is not a requirement to ship code in this project; it documents the algorithm so that independent implementations agree.

1. **Split:** subdivide the string on hyphens. Expect exactly 5 segments; reject otherwise.
2. **Validate structure:** each segment in the right character set (uppercase), correct lengths (sec. 4), correct `LEVEL`/`UNIT` grammar (secs. 7–8), `DOMAIN` in table (sec. 6).
3. **Validate segments in isolation:** confirm no leading zeros in numeric fields, no invalid characters.
4. **Canonicalize:** construct the canonical 5-segment form from the already-validated uppercase segments; ULPIN exactly 10 chars, DOMAIN 1 char, LEVEL 1–4, UNIT 1–6, CHECKSUM 2.
5. **Calculate checksum:** compute `CHECKSUM(ULPIN, DOMAIN, LEVEL, UNIT)` using section 9.3.
6. **Compare checksum:** compare the recomputed 2 characters with the supplied CHECKSUM segment; mismatch → invalid.

The document intentionally does **not** define a parser, validator, or generator as software; these steps are the conceptual contract for any future implementation.

---

## 15. Security / integrity considerations

The 2-character checksum:

- **Can:** detect single-character transcription errors, most transpositions and common typos robustly (two independent mod-36 checks: a plain checksum and a positionally weighted checksum). It is a lightweight integrity aid, useful for catching mistaken user input.
- **Cannot:** guarantee detection of every error. Two check digits only cover mod-36 arithmetic; certain paired errors can cancel outboth coefficients inches. It is not a cryptographic hash/MAC.
- **Deterministic but not reversible:** the checksum cannot be inverted to recover the VDC. This specification does not claim otherwise.
- **Not security:** the algorithm is public, uses no secret key, and provides no authenticity or tamper resistance. Anyone who knows the algorithm can compute a valid checksum for modified parts; it must not be relied on for security-sensitive integrity, anti-forgery, or message authentication.
- **Recommendation:** for security-sensitive use, layer a separate authenticated mechanism (e.g., HMAC with a key, or a canonical hash with a private signing key) outside the VDC. The VDC checksum is a *typo-detection* mechanism.

---

## 16. Non-goals

This specification explicitly does **not**:

- implement a parser, validator, or generator;
- implement or prescribe any software code, library, or program;
- define database storage schemas or models;
- define API endpoints, message payloads, or network protocols;
- establish any government adoption, mandate, or recognition;
- integrate with any government ID, cadastre, tax, or land system;
- invent official standards or claim conformance to any external government specification beyond what is stated as a GEOSIX project-level convention.

---

## 17. References / related work (project-local)

- Repository README (`README.md`, this project).
- Project directory layout (see `README.md` and repository structure) — initial scaffolding only.
- The GEOSIX VDC convention is defined entirely in this document; there is no external government reference that this project implements.
- No other external standard is required to interpret this specification ([authoritative], self-contained).

## 18. GEOSIX unit VDC lifecycle

This implementation guidance does not change the VDC syntax or checksum
specification above.

- A unit VDC is derived from `Unit -> Floor -> Building -> Parcel`: `ULPIN` is
  `Parcel.ulpin`; `DOMAIN` comes from the mapping below; `LEVEL` comes from the
  floor type and floor number; and `UNIT` is the unit identifier. Values are
  passed to the canonical generator without repair or padding.
- `DOMAIN` mapping: residential `A`, commercial `B`, industrial `C`, and
  institutional `D`. `mixed_use` has no single VDC domain and is unencodable
  until the underlying classification is made specific.
- `POST /api/v1/units/{unit_id}/vdc` derives and persists the code under a unit
  row lock. Repeating the request with unchanged source data produces the same
  code and does not change the unit timestamp.
- Unit identifier edits and floor reassignment regenerate the code in the same
  transaction. Changes to parcel ULPIN, building classification, or floor
  level are reflected as `stale` by unit reads; callers can refresh them with
  the generation endpoint. If source data cannot produce a valid VDC, the
  generation endpoint responds with 422 and existing stored values are not
  silently represented as current.
- Unit responses and `GET /api/v1/units/{unit_id}/vdc` expose `vdc_status` /
  `status` as `present`, `missing`, `stale`, or `invalid`. Status verification
  uses the same segment and checksum validation as `POST /api/v1/vdc/validate`.
- To audit legacy values, run `cd backend && python scripts/audit_vdc_codes.py`
  with the configured database URL. The command writes invalid unit IDs, code
  values, and validation errors as CSV to stdout; its row count goes to stderr.
