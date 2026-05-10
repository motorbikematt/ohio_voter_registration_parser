# Statewide School District Split Analysis
**Date:** 2026-05-09
**Source:** Ohio Secretary of State Voter File (SWVF) - Parquet partitions

## Overview
This report analyzes the overlap between voting precincts and school districts across all 88 Ohio counties. A "split precinct" is defined as any precinct where voters are divided among two or more different school districts.

## Key Findings
- **High Prevalence**: School districts frequently do not align with precinct boundaries. Most counties have at least a few split precincts.
- **Complexity**: In some counties, a single precinct can be split among as many as **5 different school districts** (e.g., Seneca and Williams counties).
- **Franklin County Exception**: Interestingly, Franklin County (25) shows 0 split precincts in this snapshot, suggesting they may align their boundaries or utilize a different reporting method in the SWVF.
- **Butler County Anomaly**: Butler County (09) shows nearly 100% of precincts are split, which warrants further investigation into how their jurisdictional data is structured.

## Statistics by County

| County | Total Precincts | Split Precincts | Max Districts per Precinct |
|---|---|---|---|
| 01 (Adams) | 21 | 5 | 2 |
| 02 (Allen) | 88 | 20 | 3 |
| 03 (Ashland) | 39 | 12 | 4 |
| 04 (Ashtabula) | 104 | 15 | 3 |
| 05 (Athens) | 50 | 9 | 2 |
| 06 (Auglaize) | 42 | 13 | 4 |
| 07 (Belmont) | 69 | 24 | 3 |
| 08 (Brown) | 33 | 13 | 3 |
| 09 (Butler) | 292 | 287 | 4 |
| 10 (Carroll) | 23 | 10 | 3 |
| 11 (Champaign) | 29 | 9 | 4 |
| 12 (Clark) | 78 | 25 | 3 |
| 13 (Clermont) | 168 | 24 | 3 |
| 14 (Clinton) | 36 | 9 | 4 |
| 15 (Columbiana) | 73 | 23 | 3 |
| 16 (Coshocton) | 23 | 14 | 3 |
| 17 (Crawford) | 35 | 17 | 3 |
| 18 (Cuyahoga) | 897 | 10 | 2 |
| 19 (Darke) | 43 | 23 | 4 |
| 20 (Defiance) | 33 | 6 | 3 |
| 21 (Delaware) | 180 | 32 | 3 |
| 22 (Erie) | 62 | 10 | 4 |
| 23 (Fairfield) | 111 | 34 | 4 |
| 24 (Fayette) | 25 | 9 | 2 |
| 25 (Franklin) | 889 | 0 | 1 |
| 26 (Fulton) | 29 | 6 | 3 |
| 27 (Gallia) | 26 | 6 | 2 |
| 28 (Geauga) | 79 | 12 | 2 |
| 29 (Greene) | 148 | 21 | 3 |
| 30 (Guernsey) | 35 | 11 | 3 |
| 31 (Hamilton) | 563 | 58 | 3 |
| 32 (Hancock) | 60 | 22 | 4 |
| 33 (Hardin) | 21 | 11 | 3 |
| 34 (Harrison) | 16 | 5 | 2 |
| 35 (Henry) | 23 | 9 | 3 |
| 36 (Highland) | 31 | 18 | 4 |
| 37 (Hocking) | 20 | 6 | 2 |
| 38 (Holmes) | 17 | 8 | 3 |
| 39 (Huron) | 46 | 18 | 3 |
| 40 (Jackson) | 30 | 7 | 2 |
| 41 (Jefferson) | 57 | 13 | 3 |
| 42 (Knox) | 53 | 14 | 4 |
| 43 (Lake) | 163 | 7 | 2 |
| 44 (Lawrence) | 84 | 13 | 2 |
| 45 (Licking) | 96 | 40 | 4 |
| 46 (Logan) | 36 | 14 | 3 |
| 47 (Lorain) | 210 | 23 | 3 |
| 48 (Lucas) | 280 | 18 | 4 |
| 49 (Madison) | 24 | 8 | 3 |
| 50 (Mahoning) | 212 | 15 | 3 |
| 51 (Marion) | 45 | 21 | 3 |
| 52 (Medina) | 124 | 13 | 3 |
| 53 (Meigs) | 27 | 3 | 2 |
| 54 (Mercer) | 36 | 13 | 4 |
| 55 (Miami) | 87 | 21 | 4 |
| 56 (Monroe) | 20 | 2 | 2 |
| 57 (Montgomery) | 381 | 46 | 3 |
| 58 (Morgan) | 13 | 1 | 3 |
| 59 (Morrow) | 33 | 0 | 1 |
| 60 (Muskingum) | 68 | 11 | 2 |
| 61 (Noble) | 19 | 9 | 3 |
| 62 (Ottawa) | 36 | 6 | 3 |
| 63 (Paulding) | 16 | 6 | 3 |
| 64 (Perry) | 33 | 13 | 3 |
| 65 (Pickaway) | 44 | 9 | 3 |
| 66 (Pike) | 22 | 3 | 2 |
| 67 (Portage) | 126 | 15 | 2 |
| 68 (Preble) | 65 | 0 | 1 |
| 69 (Putnam) | 25 | 15 | 4 |
| 70 (Richland) | 83 | 24 | 4 |
| 71 (Ross) | 65 | 14 | 2 |
| 72 (Sandusky) | 58 | 19 | 3 |
| 73 (Scioto) | 77 | 7 | 3 |
| 74 (Seneca) | 51 | 24 | 5 |
| 75 (Shelby) | 36 | 15 | 4 |
| 76 (Stark) | 274 | 69 | 4 |
| 77 (Summit) | 371 | 38 | 4 |
| 78 (Trumbull) | 158 | 31 | 4 |
| 79 (Tuscarawas) | 81 | 22 | 4 |
| 80 (Union) | 53 | 17 | 3 |
| 81 (Van Wert) | 32 | 7 | 3 |
| 82 (Vinton) | 20 | 2 | 2 |
| 83 (Warren) | 185 | 47 | 3 |
| 84 (Washington) | 50 | 8 | 2 |
| 85 (Wayne) | 66 | 25 | 4 |
| 86 (Williams) | 26 | 8 | 5 |
| 87 (Wood) | 99 | 25 | 4 |
| 88 (Wyandot) | 23 | 11 | 3 |

## Implications for Aggregation
Since school districts do not align with precincts, all school-district level analysis must be performed by grouping voters directly by their school district columns rather than aggregating precinct-level data. This ensures that every voter is correctly attributed to their district, regardless of their precinct's primary designation.
