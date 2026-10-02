https://screenerfundamentalscrapper.onrender.com

# Fundamental Scanner Guide

## 1. Main Idea

The application works in this order:

**ScanX Universe → Screener Screens → Comparison → Final Companies**

- **ScanX** creates the company universe.
- **Screener** applies the user's saved screening rules.
- **Comparison** finds companies common to the selected datasets.
- **Final CSV** contains the resulting companies.

---

## 2. ScanX

### Industry

- Industry is required.
- One or more industries can be selected.

### Sector

- Sector is optional.
- No sector selected = all sectors inside the selected industries.
- Sector selected = only the selected sectors.

### Output

ScanX saves company data as CSV.

---

## 3. Screener Screen Discovery

The application does **not** hard-code Screener screen names.

It:

1. Logs into Screener.
2. Opens **Your screens**.
3. Finds every saved screen.
4. Reads:
   - Title
   - Description
   - URL
5. Builds the groups automatically.

---

## 4. Screener Grouping

The hierarchy is:

**GROUP → SUBGROUP → ITEM**

### Group

The group is created from the **first meaningful word** in the screen title.

Example:

```text
QUALITY FINANCE
QUALITY NON FINANCE
QUALITY CAPITAL AND INFRASTRUCTURE INTENSIVE
```

→ **QUALITY**

Example:

```text
VALUATION FINANCE
VALUATION NON FINANCE
VALUATION UNDERVALUED
```

→ **VALUATION**

Common filler words such as `and`, `or`, `the`, `of`, `for`, `in`, `on`, `to`, and `with` are ignored when finding the first meaningful word.

### Subgroup

The subgroup is the **complete screen title**.

Example:

```text
QUALITY
├── QUALITY FINANCE
├── QUALITY NON FINANCE
└── QUALITY CAPITAL AND INFRASTRUCTURE INTENSIVE
```

### Item

The item is the actual Screener screen.

Its display label is:

```text
TITLE | DESCRIPTION
```

---

## 5. Group Types

### SINGLE

Only one screen exists in the group.

### PACK

All screens in the group have the same non-empty description.

The complete pack can be treated as one ready-made group.

### NORMAL

The group contains screens with different descriptions.

The user can select the required screens.

---

## 6. Running Screener Screens

### Single Mode

Run one selected screen.

### Merge Mode

Select multiple screens and combine their results.

The application keeps the companies from the selected screens and records their screen sources.

### Pack Mode

Run the complete detected pack.

No screen names are manually entered into the code.

---

## 7. Comparison Logic

### Level 1

For every selected Screener dataset:

**ScanX ∩ Screener**

This keeps companies that exist in both datasets.

```text
ScanX
  +
Screener A
  =
Level 1 result
```

### Level 2

When multiple Screener datasets are selected:

**ScanX ∩ Screener A ∩ Screener B ∩ Screener C ...**

This produces the companies common to all selected datasets.

```text
ScanX
  ↓
Screener A
  ↓
Screener B
  ↓
Screener C
  ↓
Final intersection
```

---

## 8. Complete Application Flow

```text
USER
  ↓
Select ScanX industries
  ↓
Optionally select sectors
  ↓
SCANX COMPANY UNIVERSE
  ↓
Connect to Screener
  ↓
Discover "Your screens"
  ↓
GROUP
  ↓
SUBGROUP
  ↓
ITEM / SCREEN
  ↓
Run selected Screener screens
  ↓
SAVED SCREENER CSVs
  ↓
Compare ScanX + Screener
  ↓
LEVEL 1
  ↓
LEVEL 2
  ↓
FINAL CSV
```

---

## 9. One Rule to Remember

**ScanX decides the Sector/Industry.  
Screener decides the tests.  
The application organizes the tests.  
Comparison finds the companies that survive all selected filters.**
