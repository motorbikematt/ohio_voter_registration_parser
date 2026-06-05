# Jurisdiction Name Collision Report

Generated: 2026-05-10 00:15:40  
Source: `D:\vibe\election-data (1)\source\parquet`  
Rows loaded: 7,892,613

A **collision** means the same jurisdiction name appears in voters
from more than one county partition. Name-only slugs would silently
merge these into a single output file.

---

## cities

Column: `CITY` — 212 unique values

⚠️ **26 of 212 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| REYNOLDSBURG CITY | 3 | 23, 25, 45 |
| FOSTORIA CITY | 3 | 32, 74, 87 |
| LOVELAND CITY | 3 | 13, 31, 83 |
| DUBLIN CITY | 3 | 21, 25, 80 |
| COLUMBUS CITY | 3 | 21, 23, 25 |
| RITTMAN CITY | 2 | 52, 85 |
| SPRINGBORO CITY | 2 | 57, 83 |
| COLUMBIANA CITY | 2 | 15, 50 |
| MILFORD CITY | 2 | 13, 31 |
| NORTON CITY | 2 | 77, 85 |
| KETTERING CITY | 2 | 29, 57 |
| MIDDLETOWN CITY | 2 | 09, 83 |
| VERMILION CITY | 2 | 22, 47 |
| PICKERINGTON CITY | 2 | 23, 25 |
| CENTERVILLE CITY | 2 | 29, 57 |
| NEW ALBANY CITY | 2 | 25, 45 |
| MONROE CITY | 2 | 09, 83 |
| ALLIANCE CITY | 2 | 50, 76 |
| TALLMADGE CITY | 2 | 67, 77 |
| UNION CITY | 2 | 55, 57 |
| BELLEVUE CITY | 2 | 22, 39 |
| SHARONVILLE CITY | 2 | 09, 31 |
| WESTERVILLE CITY | 2 | 21, 25 |
| HUBER HEIGHTS CITY | 2 | 55, 57 |
| DELPHOS CITY | 2 | 02, 81 |
| CANAL WINCHESTER CITY | 2 | 23, 25 |

## townships

Column: `TOWNSHIP` — 810 unique values

⚠️ **152 of 810 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| WASHINGTON TOWNSHIP | 23 | 06, 07, 14, 20, 30, 33, 34, 35, 36, 55, 56, 57, 59, 60, 63, 68, 72, 73, 75, 79, 80, 81, 83 |
| JACKSON TOWNSHIP | 19 | 06, 11, 17, 30, 33, 36, 42, 56, 57, 60, 61, 63, 64, 68, 72, 75, 80, 81, 82 |
| UNION TOWNSHIP | 17 | 06, 07, 11, 14, 24, 36, 42, 49, 55, 58, 60, 66, 73, 79, 80, 81, 83 |
| WAYNE TOWNSHIP | 14 | 01, 06, 07, 09, 11, 14, 24, 42, 56, 60, 61, 79, 83, 85 |
| WASHINGTON TWP | 14 | 08, 13, 15, 16, 19, 21, 32, 37, 40, 45, 46, 54, 65, 70 |
| JEFFERSON TOWNSHIP | 13 | 01, 14, 17, 24, 30, 42, 49, 57, 60, 61, 68, 73, 79 |
| FRANKLIN TWP | 11 | 08, 13, 15, 16, 19, 26, 40, 45, 54, 70, 71 |
| HARRISON TOWNSHIP | 11 | 11, 35, 42, 57, 60, 63, 64, 68, 73, 81, 82 |
| LIBERTY TOWNSHIP | 11 | 01, 09, 14, 17, 30, 33, 35, 36, 42, 80, 81 |
| MADISON TOWNSHIP | 11 | 09, 12, 24, 30, 36, 43, 60, 64, 72, 73, 82 |
| LIBERTY TWP | 10 | 19, 21, 23, 32, 40, 46, 54, 71, 74, 84 |
| PERRY TWP | 10 | 08, 10, 15, 16, 27, 37, 45, 46, 65, 70 |
| JACKSON TWP | 10 | 08, 13, 16, 19, 32, 40, 50, 65, 70, 74 |
| MONROE TOWNSHIP | 10 | 01, 30, 34, 35, 42, 49, 55, 60, 64, 68 |
| PERRY TOWNSHIP | 9 | 24, 43, 56, 57, 59, 60, 66, 75, 79 |
| FRANKLIN TOWNSHIP | 9 | 01, 34, 56, 59, 67, 75, 79, 83, 85 |
| SALEM TOWNSHIP | 9 | 06, 11, 36, 53, 56, 60, 75, 79, 83 |
| JEFFERSON TWP | 9 | 04, 08, 16, 40, 46, 54, 70, 71, 86 |
| MONROE TWP | 9 | 04, 10, 13, 16, 19, 45, 46, 65, 70 |
| MADISON TWP | 8 | 15, 23, 32, 40, 45, 65, 70, 86 |
| GREEN TOWNSHIP | 8 | 01, 12, 14, 24, 34, 56, 73, 75 |
| MARION TOWNSHIP | 7 | 14, 24, 33, 35, 58, 61, 66 |
| SPRINGFIELD TWP | 7 | 27, 41, 50, 70, 71, 77, 86 |
| CLAY TOWNSHIP | 7 | 06, 36, 42, 57, 60, 73, 79 |
| PLEASANT TOWNSHIP | 7 | 12, 33, 35, 42, 49, 64, 81 |
| YORK TOWNSHIP | 7 | 05, 07, 58, 72, 79, 80, 81 |
| HARRISON TWP | 7 | 10, 19, 27, 45, 46, 65, 71 |
| UNION TWP | 7 | 08, 10, 32, 45, 46, 54, 71 |
| FAIRFIELD TOWNSHIP | 6 | 09, 36, 39, 49, 50, 79 |
| GREEN TWP | 6 | 08, 27, 37, 50, 71, 85 |
| WAYNE TWP | 6 | 04, 13, 15, 19, 41, 65 |
| GOSHEN TOWNSHIP | 5 | 06, 07, 11, 33, 79 |
| CONCORD TOWNSHIP | 5 | 11, 24, 36, 43, 55 |
| ADAMS TOWNSHIP | 5 | 11, 14, 20, 30, 56 |
| RICHLAND TOWNSHIP | 5 | 07, 14, 20, 30, 82 |
| PLEASANT TWP | 5 | 08, 23, 32, 46, 74 |
| PAINT TOWNSHIP | 4 | 24, 36, 49, 85 |
| CENTER TWP | 4 | 10, 15, 54, 86 |
| SALEM TWP | 4 | 15, 41, 62, 84 |
| ADAMS TWP | 4 | 16, 19, 74, 84 |
| GERMAN TOWNSHIP | 4 | 06, 12, 34, 57 |
| CHESTER TOWNSHIP | 4 | 14, 53, 59, 85 |
| MORGAN TOWNSHIP | 4 | 09, 42, 58, 73 |
| BUTLER TWP | 4 | 15, 19, 54, 70 |
| BROWN TOWNSHIP | 4 | 42, 55, 63, 82 |
| CENTER TOWNSHIP | 4 | 30, 56, 58, 61 |
| PIKE TOWNSHIP | 4 | 12, 42, 49, 64 |
| SCIOTO TWP | 4 | 21, 40, 65, 71 |
| CLINTON TOWNSHIP | 4 | 42, 75, 82, 85 |
| CANAAN TOWNSHIP | 4 | 05, 49, 59, 85 |
| HOPEWELL TWP | 3 | 45, 54, 74 |
| BERLIN TWP | 3 | 21, 22, 50 |
| ALLEN TWP | 3 | 19, 32, 62 |
| ORANGE TWP | 3 | 10, 21, 32 |
| DEERFIELD TOWNSHIP | 3 | 58, 67, 83 |
| BENTON TOWNSHIP | 3 | 56, 63, 66 |
| BETHEL TOWNSHIP | 3 | 12, 55, 56 |
| MILFORD TOWNSHIP | 3 | 09, 20, 42 |
| THOMPSON TWP | 3 | 21, 28, 74 |
| TROY TWP | 3 | 21, 28, 70 |
| OXFORD TOWNSHIP | 3 | 09, 30, 79 |
| DOVER TOWNSHIP | 3 | 05, 79, 80 |
| PIKE TWP | 3 | 08, 16, 26 |
| NEWTON TOWNSHIP | 3 | 55, 60, 66 |
| OXFORD TWP | 3 | 16, 21, 22 |
| NOBLE TOWNSHIP | 3 | 06, 20, 61 |
| DARBY TOWNSHIP | 3 | 49, 65, 80 |
| RICHLAND TWP | 3 | 19, 23, 46 |
| VERNON TOWNSHIP | 3 | 14, 17, 73 |
| BRUSH CREEK TOWNSHIP | 3 | 01, 60, 73 |
| WALNUT TWP | 3 | 23, 27, 65 |
| RUSH TOWNSHIP | 3 | 11, 73, 79 |
| HUNTINGTON TWP | 3 | 08, 27, 71 |
| BROWN TWP | 3 | 10, 19, 21 |
| MARION TWP | 3 | 32, 37, 54 |
| MILTON TWP | 3 | 40, 50, 85 |
| BLOOM TOWNSHIP | 2 | 58, 73 |
| PENN TOWNSHIP | 2 | 36, 58 |
| CLAY TWP | 2 | 27, 62 |
| MILLCREEK TWP | 2 | 16, 86 |
| PLYMOUTH TWP | 2 | 04, 70 |
| ELK TOWNSHIP | 2 | 61, 82 |
| KNOX TOWNSHIP | 2 | 30, 82 |
| SYMMES TWP. | 2 | 31, 44 |
| SALT CREEK TOWNSHIP | 2 | 60, 85 |
| HOPEWELL TOWNSHIP | 2 | 60, 64 |
| SENECA TOWNSHIP | 2 | 56, 61 |
| BUTLER TOWNSHIP | 2 | 42, 57 |
| ATHENS TOWNSHIP | 2 | 05, 34 |
| GREENFIELD TWP | 2 | 23, 27 |
| GRANVILLE TWP | 2 | 45, 54 |
| BENTON TWP | 2 | 37, 62 |
| TIFFIN TOWNSHIP | 2 | 01, 20 |
| PLEASANT TWP. | 2 | 51, 69 |
| EDEN TWP | 2 | 45, 74 |
| SALTCREEK TWP | 2 | 37, 65 |
| WHEELING TOWNSHIP | 2 | 07, 30 |
| PERRY TWP. | 2 | 44, 69 |
| TROY TOWNSHIP | 2 | 05, 59 |
| MIAMI TWP | 2 | 13, 46 |
| SPRINGFIELD TOWNSHIP | 2 | 12, 60 |
| MANCHESTER TOWNSHIP | 2 | 01, 58 |
| TURTLECREEK TOWNSHIP | 2 | 75, 83 |
| KNOX TWP | 2 | 15, 41 |
| PERU TOWNSHIP | 2 | 39, 59 |
| AUBURN TOWNSHIP | 2 | 17, 79 |
| AMANDA TWP | 2 | 23, 32 |
| CASS TWP | 2 | 32, 70 |
| VALLEY TOWNSHIP | 2 | 30, 73 |
| ORANGE TOWNSHIP | 2 | 53, 75 |
| STOCK TOWNSHIP | 2 | 34, 61 |
| CONCORD TWP | 2 | 21, 71 |
| BEAVER TOWNSHIP | 2 | 61, 66 |
| CLARK TWP | 2 | 08, 16 |
| MAD RIVER TOWNSHIP | 2 | 11, 12 |
| HANOVER TWP | 2 | 15, 45 |
| FREEDOM TOWNSHIP | 2 | 35, 67 |
| MOOREFIELD TOWNSHIP | 2 | 12, 34 |
| RICHFIELD TOWNSHIP | 2 | 35, 48 |
| SCOTT TOWNSHIP | 2 | 01, 72 |
| FAIRFIELD TWP | 2 | 15, 84 |
| PORTAGE TWP | 2 | 32, 62 |
| TOWNSEND TOWNSHIP | 2 | 39, 72 |
| PARIS TOWNSHIP | 2 | 67, 80 |
| LEE TOWNSHIP | 2 | 05, 56 |
| WARREN TOWNSHIP | 2 | 07, 79 |
| YORK TWP | 2 | 19, 26 |
| VAN BUREN TWP | 2 | 19, 32 |
| OLIVE TOWNSHIP | 2 | 53, 61 |
| HIGHLAND TOWNSHIP | 2 | 20, 60 |
| SANDUSKY TWP | 2 | 70, 72 |
| CLEARCREEK TOWNSHIP | 2 | 57, 83 |
| CLINTON TWP | 2 | 26, 74 |
| LOUDON TWP | 2 | 10, 74 |
| CONGRESS TOWNSHIP | 2 | 59, 85 |
| OHIO TWP | 2 | 13, 27 |
| WASHINGTON | 2 | 38, 76 |
| HARMONY TOWNSHIP | 2 | 12, 59 |
| DELAWARE TWP | 2 | 21, 32 |
| COLUMBIA TOWNSHIP | 2 | 47, 53 |
| SPENCER TOWNSHIP | 2 | 30, 48 |
| MORGAN TWP | 2 | 04, 27 |
| BLOOMFIELD TWP | 2 | 40, 46 |
| EAGLE TWP | 2 | 08, 32 |
| BLOOM TWP | 2 | 23, 74 |
| RUSHCREEK TWP | 2 | 23, 46 |
| GOSHEN TWP | 2 | 13, 50 |
| WARREN TWP | 2 | 41, 84 |
| MEIGS TOWNSHIP | 2 | 01, 60 |
| DEERCREEK TOWNSHIP | 2 | 49, 65 |
| UNION TWP. | 2 | 44, 69 |
| FLORENCE TWP | 2 | 22, 86 |

## villages

Column: `VILLAGE` — 645 unique values

⚠️ **37 of 645 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| MINERVA VILLAGE | 3 | 10, 15, 76 |
| BRADFORD VILLAGE | 2 | 19, 55 |
| PLYMOUTH VILLAGE | 2 | 39, 70 |
| WILSON VILLAGE | 2 | 07, 56 |
| BUCHTEL VILLAGE | 2 | 05, 37 |
| BALTIC VILLAGE | 2 | 38, 79 |
| GRATIOT VILLAGE | 2 | 45, 60 |
| SCOTT VILLAGE | 2 | 63, 81 |
| FREDERICKTOWN VILLAGE | 2 | 42, 85 |
| YORKVILLE VILLAGE | 2 | 07, 41 |
| PLAIN CITY VILLAGE | 2 | 49, 80 |
| CRESTON VILLAGE | 2 | 52, 85 |
| GREEN SPRINGS VILLAGE | 2 | 72, 74 |
| MOGADORE VILLAGE | 2 | 67, 77 |
| ADENA VILLAGE | 2 | 34, 41 |
| WASHINGTONVILLE VILLAGE | 2 | 15, 50 |
| BUCKEYE LAKE VILLAGE | 2 | 23, 45 |
| BLUFFTON VILLAGE | 2 | 02, 32 |
| SWANTON VILLAGE | 2 | 26, 48 |
| LITHOPOLIS VILLAGE | 2 | 23, 25 |
| BURKETTSVILLE VILLAGE | 2 | 19, 54 |
| HARVEYSBURG VILLAGE | 2 | 14, 83 |
| LOUDONVILLE VILLAGE | 2 | 03, 38 |
| NEW HOLLAND VILLAGE | 2 | 24, 65 |
| CRESTLINE VILLAGE | 2 | 17, 70 |
| BUTLER VILLAGE | 2 | 70, 83 |
| HARRISBURG VILLAGE | 2 | 25, 65 |
| MAGNOLIA VILLAGE | 2 | 10, 76 |
| ROSEVILLE VILLAGE | 2 | 60, 64 |
| CLIFTON VILLAGE | 2 | 12, 29 |
| UTICA VILLAGE | 2 | 42, 45 |
| COLLEGE CORNER VILLAGE | 2 | 09, 68 |
| MILAN VILLAGE | 2 | 22, 39 |
| RIDGEWAY VILLAGE | 2 | 33, 46 |
| VERONA VILLAGE | 2 | 57, 68 |
| LYNCHBURG VILLAGE | 2 | 14, 36 |
| WEST MILTON VILLAGE | 2 | 55, 87 |

## local_school_districts

Column: `LOCAL_SCHOOL_DISTRICT` — 366 unique values

⚠️ **182 of 366 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| MIAMI TRACE LOCAL SD (FAYETTE) | 6 | 14, 24, 36, 49, 65, 71 |
| BLANCHESTER LOCAL SD (CLINTON) | 4 | 08, 13, 14, 83 |
| BUCKEYE CENTRAL LOCAL SD (CRAWFORD) | 4 | 17, 39, 70, 74 |
| MINSTER LOCAL SD (AUGLAIZE) | 4 | 06, 19, 54, 75 |
| WEST HOLMES LOCAL SD (HOLMES) | 4 | 03, 16, 38, 85 |
| EAST KNOX LOCAL SD (KNOX) | 3 | 16, 42, 45 |
| LYNCHBURG-CLAY LOCAL SD (HIGHLAND) | 3 | 08, 14, 36 |
| LOGAN-HOCKING LOCAL SD (HOCKING) | 3 | 37, 64, 82 |
| UPPER SCIOTO VALLEY LOCAL SD (HARDIN) | 3 | 06, 33, 46 |
| NORTHWEST LOCAL SD (STARK) | 3 | 76, 77, 85 |
| PATRICK HENRY LOCAL SD (HENRY) | 3 | 35, 69, 87 |
| ROLLING HILLS LOCAL SD (GUERNSEY) | 3 | 30, 60, 61 |
| SWITZERLAND OF OHIO LOCAL SD (MONROE) | 3 | 07, 56, 61 |
| BENJAMIN LOGAN LOCAL SD (LOGAN) | 3 | 33, 46, 80 |
| EASTERN LOCAL SD (PIKE) | 3 | 40, 66, 73 |
| TRIAD LOCAL SD (CHAMPAIGN) | 3 | 11, 46, 80 |
| NEW LONDON LOCAL SD (HURON) | 3 | 03, 39, 47 |
| EDISON LOCAL SD (JEFFERSON) | 3 | 10, 34, 41 |
| FAYETTEVILLE-PERRY LOCAL SD (BROWN) | 3 | 08, 14, 36 |
| PLYMOUTH-SHILOH LOCAL SD (RICHLAND) | 3 | 17, 39, 70 |
| PREBLE SHAWNEE LOCAL SD (PREBLE) | 3 | 09, 57, 68 |
| CENTERBURG LOCAL SD (KNOX) | 3 | 21, 42, 45 |
| SPENCERVILLE LOCAL SD (ALLEN) | 3 | 02, 06, 81 |
| SOUTHERN LOCAL SD (COLUMBIANA) | 3 | 10, 15, 41 |
| WEST BRANCH LOCAL SD (MAHONING) | 3 | 15, 50, 67 |
| LAKOTA LOCAL SD (SANDUSKY) | 3 | 72, 74, 87 |
| NORTHRIDGE LOCAL SD (LICKING) | 3 | 21, 42, 45 |
| MOHAWK LOCAL SD (WYANDOT) | 3 | 17, 74, 88 |
| WAYNE TRACE LOCAL SD (PAULDING) | 3 | 63, 69, 81 |
| JACKSON CENTER LOCAL SD (SHELBY) | 3 | 06, 46, 75 |
| EASTERN LOCAL SD (BROWN) | 3 | 01, 08, 36 |
| MINERVA LOCAL SD (STARK) | 3 | 10, 15, 76 |
| VINTON COUNTY LOCAL SD (VINTON) | 3 | 37, 40, 82 |
| BUCKEYE VALLEY LOCAL SD (DELAWARE) | 3 | 21, 51, 80 |
| NEW BREMEN LOCAL SD (AUGLAIZE) | 3 | 06, 54, 75 |
| ANTHONY WAYNE LOCAL SD (LUCAS) | 3 | 26, 48, 87 |
| FORT FRYE LOCAL SD (WASH) | 3 | 58, 61, 84 |
| ELGIN LOCAL SD (MARION) | 3 | 21, 33, 51 |
| MARION LOCAL SD (MERCER) | 3 | 06, 19, 54 |
| VANLUE LOCAL SD (HANCOCK) | 3 | 32, 74, 88 |
| OTSEGO LOCAL SD (WOOD) | 3 | 35, 48, 87 |
| SANDY VALLEY LOCAL SD (STARK) | 3 | 10, 76, 79 |
| RIVER VIEW LOCAL SD (COSHOCTON) | 3 | 16, 45, 60 |
| BUCKEYE LOCAL SD (JEFFERSON) | 3 | 07, 34, 41 |
| RIVERDALE LOCAL SD (HANCOCK) | 3 | 32, 33, 88 |
| NORTHERN LOCAL SD (PERRY) | 3 | 23, 45, 64 |
| GARAWAY LOCAL SD (TUSC) | 3 | 16, 38, 79 |
| NOBLE LOCAL SD (NOBLE) | 3 | 30, 56, 61 |
| BLACK RIVER LOCAL SD (MEDINA) | 3 | 03, 47, 52 |
| WAYNEDALE LOCAL SD (WAYNE) | 3 | 38, 76, 85 |
| ALEXANDER LOCAL SD (ATHENS) | 3 | 05, 53, 82 |
| RIDGEWOOD LOCAL SD (COSHOCTON) | 3 | 16, 30, 79 |
| PARKWAY LOCAL SD (MERCER) | 3 | 06, 54, 81 |
| RIDGEDALE LOCAL SD (MARION) | 3 | 17, 51, 88 |
| WAYNESFIELD-GOSHEN LOCAL SD (AUGLAIZE) | 3 | 02, 06, 46 |
| MCCOMB LOCAL SD (HANCOCK) | 3 | 32, 69, 87 |
| GREENEVIEW LOCAL SD (GREENE) | 3 | 14, 24, 29 |
| TRI-COUNTY NORTH LSD (PREBLE) | 3 | 19, 57, 68 |
| FAIRFIELD UNION LOCAL SD (FAIRFIELD) | 3 | 23, 37, 64 |
| GALLIA COUNTY LOCAL SD (GALLIA) | 2 | 27, 40 |
| BELLBROOK-SUGARCREEK LOCAL SD (GREENE) | 2 | 29, 83 |
| CHARDON LOCAL SD (GEAUGA) | 2 | 28, 43 |
| JOHNSTOWN-MONROE LOCAL SD (LICKING) | 2 | 21, 45 |
| FEDERAL HOCKING LOCAL SD (ATHENS) | 2 | 05, 58 |
| RIVERSIDE LOCAL SD (LAKE) | 2 | 28, 43 |
| PANDORA-GILBOA LOCAL SD (PUTNAM) | 2 | 02, 69 |
| NATIONAL TRAIL LOCAL SD (PREBLE) | 2 | 19, 68 |
| COLLEGE CORNER LOCAL SD (PREBLE) | 2 | 09, 68 |
| INDIAN LAKE LOCAL SD (LOGAN) | 2 | 06, 46 |
| HIGHLAND LOCAL SD (MEDINA) | 2 | 52, 77 |
| GOSHEN LOCAL SD (CLERMONT) | 2 | 13, 83 |
| MOGADORE LOCAL SD (SUMMIT) | 2 | 67, 77 |
| TEAYS VALLEY LOCAL SD (PICKAWAY) | 2 | 23, 65 |
| ADAMS COUNTY/OH VALLEY LSD (ADAMS) | 2 | 01, 36 |
| EAST HOLMES LOCAL SD (HOLMES) | 2 | 38, 85 |
| JACKSON-MILTON LOCAL SD (MAHONING) | 2 | 50, 78 |
| SOUTHERN LOCAL SD (PERRY) | 2 | 37, 64 |
| NORTH BALTIMORE LOCAL SD (WOOD) | 2 | 32, 87 |
| TRI-VALLEY LOCAL SD (MUSK) | 2 | 16, 60 |
| FAIRLAWN LOCAL SD (SHELBY) | 2 | 44, 75 |
| TRIMBLE LOCAL SD (ATHENS) | 2 | 05, 58 |
| FIRELANDS LOCAL SD (LORAIN) | 2 | 22, 47 |
| EAST MUSKINGUM LOCAL SD (MUSK) | 2 | 30, 60 |
| LOGAN ELM LOCAL SD (PICKAWAY) | 2 | 37, 65 |
| ELMWOOD LOCAL SD (WOOD) | 2 | 32, 87 |
| LAKE LOCAL SD (WOOD) | 2 | 62, 87 |
| CARLISLE LOCAL SD (WARREN) | 2 | 57, 83 |
| KIRTLAND LOCAL SD (LAKE) | 2 | 28, 43 |
| WEST MUSKINGUM LOCAL SD (MUSK) | 2 | 45, 60 |
| NEWTON LOCAL SD (MIAMI) | 2 | 19, 55 |
| CRESTVIEW LOCAL SD (RICHLAND) | 2 | 03, 70 |
| DANVILLE LOCAL SD (KNOX) | 2 | 38, 42 |
| FRANKLIN-MONROE LOCAL SD (DARKE) | 2 | 19, 55 |
| MIAMI EAST LOCAL SD (MIAMI) | 2 | 11, 55 |
| CARDINAL LOCAL SD (GEAUGA) | 2 | 28, 78 |
| NORTH FORK LOCAL SD (LICKING) | 2 | 42, 45 |
| WAYNE LOCAL SD (WARREN) | 2 | 29, 83 |
| SOUTHWEST LICKING LOCAL SD (LICKING) | 2 | 23, 45 |
| NEW KNOXVILLE LOCAL SD (AUGLAIZE) | 2 | 06, 75 |
| BROOKVILLE LOCAL SD (MONTG) | 2 | 57, 68 |
| MARGARETTA LOCAL SD (ERIE) | 2 | 22, 72 |
| CENTRAL LOCAL SD (DEFIANCE) | 2 | 20, 86 |
| RIVERSIDE LOCAL SD (LOGAN) | 2 | 46, 75 |
| SWANTON LOCAL SD (FULTON) | 2 | 26, 48 |
| BERNE UNION LOCAL SD (FAIRFIELD) | 2 | 23, 37 |
| CEDAR CLIFF LOCAL SD (GREENE) | 2 | 12, 29 |
| COLUMBUS GROVE LOCAL SD (PUTNAM) | 2 | 02, 69 |
| OLD FORT LOCAL SD (SENECA) | 2 | 72, 74 |
| NORTHWEST LOCAL SD (HAMILTON) | 2 | 09, 31 |
| BROWN LOCAL SD (CARROLL) | 2 | 10, 76 |
| BRIGHT LOCAL SD (HIGHLAND) | 2 | 01, 36 |
| TRIWAY LOCAL SD (WAYNE) | 2 | 38, 85 |
| NORTHWESTERN LOCAL SD (CLARK) | 2 | 11, 12 |
| GRAHAM LOCAL SD (CHAMPAIGN) | 2 | 11, 75 |
| WARREN LOCAL SD (WASH) | 2 | 05, 84 |
| NORWAYNE LOCAL SD (WAYNE) | 2 | 52, 85 |
| EAST CLINTON LOCAL SD (CLINTON) | 2 | 14, 36 |
| OTTOVILLE LOCAL SD (PUTNAM) | 2 | 63, 69 |
| ARCADIA LOCAL SD (HANCOCK) | 2 | 32, 74 |
| JACKSON LOCAL SD (STARK) | 2 | 76, 77 |
| SOUTHWEST LOCAL SD (HAMILTON) | 2 | 09, 31 |
| LUCAS LOCAL LOCAL SD (RICHLAND) | 2 | 03, 70 |
| RUSSIA LOCAL SD (SHELBY) | 2 | 19, 75 |
| BOTKINS LOCAL SD (SHELBY) | 2 | 06, 75 |
| ARCHBOLD-AREA LOCAL SD (FULTON) | 2 | 26, 35 |
| TUSCARAWAS VALLEY LOCAL SD (TUSC) | 2 | 76, 79 |
| HARDIN NORTHERN LOCAL SD (HARDIN) | 2 | 32, 33 |
| GREEN LOCAL SD (SCIOTO) | 2 | 73, 77 |
| MONROEVILLE LOCAL SD (HURON) | 2 | 22, 39 |
| RIDGEMONT LOCAL SD (HARDIN) | 2 | 33, 46 |
| FAIRFIELD LOCAL SD (HIGHLAND) | 2 | 14, 36 |
| HILLSDALE LOCAL SD (ASHLAND) | 2 | 03, 85 |
| SHAWNEE LOCAL SD (ALLEN) | 2 | 02, 06 |
| SOUTHEAST LOCAL SD (PORTAGE) | 2 | 29, 67 |
| LAKE LOCAL SD (STARK) | 2 | 67, 76 |
| EDISON LOCAL SD (ERIE) | 2 | 22, 39 |
| TECUMSEH LOCAL SD (CLARK) | 2 | 12, 55 |
| NORTH UNION LOCAL SD (UNION) | 2 | 21, 80 |
| CLINTON-MASSIE LOCAL SD (CLINTON) | 2 | 14, 83 |
| NORTHMOR LOCAL SD (MORROW) | 2 | 51, 70 |
| MADISON LOCAL SD (LAKE) | 2 | 28, 43 |
| CLEAR FORK VALLEY LOCAL SD (RICHLAND) | 2 | 42, 70 |
| SOUTH CENTRAL LOCAL SD (HURON) | 2 | 39, 70 |
| FORT RECOVERY LOCAL SD (MERCER) | 2 | 19, 54 |
| WYNFORD LOCAL SD (CRAWFORD) | 2 | 17, 88 |
| LITTLE MIAMI LOCAL SD (WARREN) | 2 | 13, 83 |
| FRANKLIN LOCAL SD (MUSK) | 2 | 60, 64 |
| FOREST HILLS LOCAL SD (HAMILTON) | 2 | 13, 31 |
| EVERGREEN LOCAL SD (FULTON) | 2 | 26, 48 |
| SYMMES VALLEY LOCAL SD (LAWRENCE) | 2 | 27, 44 |
| WOODMORE LOCAL LOCAL SD (SANDUSKY) | 2 | 62, 72 |
| CLERMONT NORTHEASTERN LOCAL SD (CLERMONT) | 2 | 08, 13 |
| WILLIAMSBURG LOCAL SD (CLERMONT) | 2 | 08, 13 |
| WEATHERSFIELD LOCAL SD (TRUMBULL) | 2 | 50, 78 |
| OSNABURG LOCAL SD (STARK) | 2 | 10, 76 |
| LIBERTY CENTER LOCAL SD (HENRY) | 2 | 26, 35 |
| ADENA LOCAL SD (ROSS) | 2 | 65, 71 |
| WASHINGTON LOCAL SD (LUCAS) | 2 | 48, 73 |
| VALLEY VIEW LOCAL SD (MONTG) | 2 | 57, 68 |
| LICKING VALLEY LOCAL SD (LICKING) | 2 | 45, 60 |
| PETTISVILLE LOCAL SD (FULTON) | 2 | 26, 35 |
| NORTHEASTERN LOCAL SD (CLARK) | 2 | 11, 12 |
| WESTERN RESERVE LOCAL SD (HURON) | 2 | 22, 39 |
| FORT LORAMIE LOCAL SD (SHELBY) | 2 | 19, 75 |
| NORTHWESTERN LOCAL SD (WAYNE) | 2 | 03, 85 |
| WESTFALL LOCAL SD (PICKAWAY) | 2 | 49, 65 |
| FAIRBANKS LOCAL SD (UNION) | 2 | 49, 80 |
| MONROE LOCAL SD (BUTLER) | 2 | 09, 83 |
| SPRINGFIELD LOCAL SD (SUMMIT) | 2 | 67, 77 |
| EDGERTON LOCAL SD (WILLIAMS) | 2 | 20, 86 |
| SENECA EAST LOCAL SD (SENECA) | 2 | 39, 74 |
| JONATHAN ALDER LOCAL SD (MADISON) | 2 | 49, 80 |
| OAK HILL UNION LOCAL SD (JACKSON) | 2 | 40, 44 |
| CONOTTON VALLEY-UNION LOCAL SD (HARRISON) | 2 | 10, 34 |
| MAPLETON LOCAL SD (ASHLAND) | 2 | 03, 47 |
| MADISON-PLAINS LOCAL SD (MADISON) | 2 | 24, 49 |
| FAIRLESS LOCAL SD (STARK) | 2 | 76, 79 |
| WEST LIBERTY-SALEM LOCAL SD (CHAMPAIGN) | 2 | 11, 46 |
| SCIOTO VALLEY LOCAL SD (PIKE) | 2 | 66, 73 |
| TUSLAW LOCAL SD (STARK) | 2 | 76, 85 |
| VERMILION LOCAL SD (ERIE) | 2 | 22, 47 |
| ST HENRY CONSOLIDATED LOCAL SD (MERCER) | 2 | 19, 54 |

## city_school_districts

Column: `CITY_SCHOOL_DISTRICT` — 183 unique values

⚠️ **35 of 183 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| BELLEVUE CITY SD | 4 | 22, 39, 72, 74 |
| HARRISON HILLS CITY SD | 4 | 07, 10, 34, 41 |
| FAIRBORN CITY SD | 3 | 12, 29, 57 |
| NORTHMONT CITY SD | 3 | 19, 55, 57 |
| LOVELAND CITY SD | 3 | 13, 31, 83 |
| FOSTORIA CITY SD | 3 | 32, 74, 87 |
| PRINCETON CITY SD | 3 | 09, 31, 83 |
| ALLIANCE CITY SD | 3 | 15, 50, 76 |
| BOWLING GREEN CITY SD | 2 | 35, 87 |
| REYNOLDSBURG CITY SD | 2 | 23, 45 |
| SPRINGBORO COMMUNITY CITY SD | 2 | 57, 83 |
| TALAWANDA CITY SD | 2 | 09, 68 |
| STOW-MUNROE FALLS CITY SD | 2 | 67, 77 |
| STRONGSVILLE CITY SD | 2 | 18, 47 |
| MIDDLETOWN CITY SD | 2 | 09, 83 |
| WILLARD CITY SD | 2 | 17, 39 |
| WILMINGTON CITY SD | 2 | 14, 29 |
| AURORA CITY SD | 2 | 67, 77 |
| TALLMADGE CITY SD | 2 | 67, 77 |
| KETTERING CITY SD | 2 | 29, 57 |
| EDGEWOOD CITY SD | 2 | 09, 68 |
| WAVERLY CITY SD | 2 | 66, 71 |
| ASHLAND CITY SD | 2 | 03, 70 |
| XENIA COMMUNITY CITY SD | 2 | 29, 83 |
| DEFIANCE CITY SD | 2 | 20, 63 |
| DUBLIN CITY SD | 2 | 21, 80 |
| NELSONVILLE-YORK CITY SD | 2 | 05, 37 |
| MASON CITY SD | 2 | 09, 83 |
| BEAVERCREEK CITY SD | 2 | 29, 57 |
| OLMSTED FALLS CITY SD | 2 | 18, 47 |
| GALION CITY SD | 2 | 17, 70 |
| KENTON CITY SD | 2 | 33, 88 |
| HUBER HEIGHTS CITY SD | 2 | 29, 57 |
| DELPHOS CITY SD | 2 | 02, 81 |
| SIDNEY CITY SD | 2 | 46, 75 |

## exempted_vill_school_districts

Column: `EXEMPTED_VILL_SCHOOL_DISTRICT` — 48 unique values

⚠️ **24 of 48 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| LOUDONVILLE-PERRYSVILLE EX VILL SD (ASHLAND) | 4 | 03, 38, 42, 70 |
| BRADFORD EX VILL SD (MIAMI) | 3 | 19, 55, 75 |
| UPPER SANDUSKY EX VILL SD (WYANDOT) | 3 | 17, 51, 88 |
| GREENFIELD EX VILL SD (HIGHLAND) | 3 | 24, 36, 71 |
| NEWCOMERSTOWN EX VILL SD (TUSC) | 3 | 16, 30, 79 |
| MECHANICSBURG EX VILL SD (CHAMPAIGN) | 2 | 11, 49 |
| CRESTLINE EX VILL SD (CRAWFORD) | 2 | 17, 70 |
| CHAGRIN FALLS EX VILL SD (CUY) | 2 | 18, 28 |
| VERSAILLES EX VILL SD (DARKE) | 2 | 19, 75 |
| MILFORD EX VILL SD (CLERMONT) | 2 | 13, 31 |
| LEETONIA EX VILL SD (COLUMBIANA) | 2 | 15, 50 |
| YELLOW SPRINGS EX VILL SD (GREENE) | 2 | 12, 29 |
| CLYDE-GREEN SPRINGS EX VILL SD (SANDUSKY) | 2 | 72, 74 |
| WELLINGTON EX VILL SD (LORAIN) | 2 | 39, 47 |
| CAREY EX VILL SD (WYANDOT) | 2 | 74, 88 |
| HUBBARD EX VILL SD (TRUMBULL) | 2 | 50, 78 |
| PAULDING EX VILL SD (PAULDING) | 2 | 63, 69 |
| RITTMAN EX VILL SD (WAYNE) | 2 | 52, 85 |
| ADA EX VILL SD (HARDIN) | 2 | 32, 33 |
| MENTOR EX VILL SD (LAKE) | 2 | 28, 43 |
| CALDWELL EX VILL SD (NOBLE) | 2 | 61, 84 |
| BLUFFTON EX VILL SD (ALLEN) | 2 | 02, 32 |
| COLUMBIANA EX VILL SD (COLUMBIANA) | 2 | 15, 50 |
| GIBSONBURG EX VILL SD (SANDUSKY) | 2 | 72, 87 |

## state_senate_districts

Column: `STATE_SENATE_DISTRICT` — 33 unique values

⚠️ **20 of 33 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| 17 | 10 | 24, 27, 36, 37, 40, 44, 64, 66, 71, 82 |
| 01 | 10 | 20, 26, 32, 33, 35, 46, 63, 69, 81, 86 |
| 30 | 10 | 05, 07, 30, 34, 41, 53, 56, 58, 61, 84 |
| 26 | 7 | 17, 51, 59, 72, 74, 80, 88 |
| 12 | 7 | 02, 06, 11, 19, 46, 54, 75 |
| 02 | 5 | 22, 39, 48, 62, 87 |
| 31 | 5 | 30, 60, 76, 79, 85 |
| 05 | 5 | 09, 19, 55, 57, 68 |
| 14 | 4 | 01, 08, 13, 73 |
| 19 | 4 | 16, 21, 38, 42 |
| 22 | 3 | 03, 52, 70 |
| 10 | 3 | 12, 14, 29 |
| 27 | 3 | 28, 67, 77 |
| 03 | 3 | 25, 49, 65 |
| 33 | 3 | 10, 15, 50 |
| 20 | 3 | 23, 45, 64 |
| 32 | 3 | 04, 28, 78 |
| 18 | 2 | 18, 43 |
| 07 | 2 | 31, 83 |
| 13 | 2 | 39, 47 |

## state_rep_districts

Column: `STATE_REPRESENTATIVE_DISTRICT` — 99 unique values

⚠️ **37 of 99 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| 95 | 6 | 05, 07, 30, 34, 58, 61 |
| 81 | 4 | 20, 26, 35, 86 |
| 92 | 4 | 37, 64, 71, 82 |
| 91 | 4 | 24, 36, 66, 71 |
| 87 | 4 | 17, 51, 59, 88 |
| 82 | 4 | 20, 63, 69, 81 |
| 12 | 3 | 25, 49, 65 |
| 85 | 3 | 11, 46, 75 |
| 93 | 3 | 27, 40, 44 |
| 98 | 3 | 16, 38, 42 |
| 40 | 3 | 09, 57, 68 |
| 35 | 3 | 28, 67, 77 |
| 96 | 3 | 07, 41, 56 |
| 44 | 3 | 48, 62, 87 |
| 83 | 3 | 32, 33, 46 |
| 69 | 3 | 23, 45, 64 |
| 84 | 3 | 06, 19, 54 |
| 90 | 3 | 01, 08, 73 |
| 94 | 3 | 05, 53, 84 |
| 89 | 3 | 22, 39, 62 |
| 71 | 3 | 12, 14, 29 |
| 65 | 2 | 04, 78 |
| 86 | 2 | 51, 80 |
| 67 | 2 | 03, 52 |
| 23 | 2 | 18, 43 |
| 63 | 2 | 08, 13 |
| 97 | 2 | 30, 60 |
| 78 | 2 | 02, 06 |
| 80 | 2 | 19, 55 |
| 61 | 2 | 21, 42 |
| 59 | 2 | 15, 50 |
| 88 | 2 | 72, 74 |
| 51 | 2 | 76, 79 |
| 99 | 2 | 04, 28 |
| 45 | 2 | 09, 48 |
| 79 | 2 | 10, 15 |
| 54 | 2 | 39, 47 |

## congressional_districts

Column: `CONGRESSIONAL_DISTRICT` — 15 unique values

⚠️ **13 of 15 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| 02 | 16 | 01, 05, 08, 13, 27, 37, 40, 44, 53, 58, 64, 66, 71, 73, 82, 84 |
| 04 | 14 | 02, 06, 11, 12, 21, 33, 46, 51, 54, 59, 70, 75, 80, 81 |
| 12 | 11 | 16, 21, 23, 30, 38, 42, 45, 56, 60, 61, 64 |
| 06 | 10 | 07, 10, 15, 34, 38, 41, 50, 76, 79, 85 |
| 09 | 10 | 20, 22, 26, 35, 48, 62, 63, 69, 86, 87 |
| 05 | 10 | 17, 32, 39, 47, 48, 70, 72, 74, 87, 88 |
| 15 | 7 | 12, 24, 25, 36, 49, 55, 65 |
| 14 | 6 | 04, 28, 43, 50, 67, 78 |
| 08 | 5 | 09, 19, 31, 55, 68 |
| 07 | 4 | 03, 18, 52, 85 |
| 13 | 3 | 67, 76, 77 |
| 01 | 3 | 14, 31, 83 |
| 10 | 3 | 09, 29, 57 |

## county_court_districts

Column: `COUNTY_COURT_DISTRICT` — 2 unique values

✅ **No collisions.**

## municipal_court_districts

Column: `MUNICIPAL_COURT_DISTRICT` — 67 unique values

⚠️ **2 of 67 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| BELLEVUE | 3 | 22, 39, 72 |
| VERMILLION | 2 | 22, 47 |

## court_of_appeals

Column: `COURT_OF_APPEALS` — 12 unique values

⚠️ **9 of 12 names span multiple counties.**

| Name | Counties (n) | County numbers |
|------|:---:|---|
| 03 | 17 | 02, 06, 17, 20, 32, 33, 35, 46, 51, 54, 63, 69, 74, 75, 80, 81, 88 |
| 05 | 15 | 03, 16, 21, 23, 30, 38, 42, 45, 58, 59, 60, 64, 70, 76, 79 |
| 04 | 14 | 01, 05, 27, 36, 37, 40, 44, 53, 65, 66, 71, 73, 82, 84 |
| 12 | 8 | 08, 09, 13, 14, 24, 49, 68, 83 |
| 06 | 8 | 22, 26, 39, 48, 62, 72, 86, 87 |
| 07 | 8 | 07, 10, 15, 34, 41, 50, 56, 61 |
| 02 | 6 | 11, 12, 19, 29, 55, 57 |
| 11 | 5 | 04, 28, 43, 67, 78 |
| 09 | 4 | 47, 52, 77, 85 |

---

**Result:** Collisions detected. The groupings script must use a composite key (`COUNTY_NUMBER` + name) for county-scoped types, or confirm that cross-county presence reflects a single real jurisdiction (e.g. legislative districts, multi-county cities).