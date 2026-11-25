# Frozen municipal journey validation

Passed: 14/14.

Expected software outcomes for source-backed points, not independently verified physical routes or human usability results.

| Case | Expected | Actual | Network m | Path / optimality | Seconds |
| --- | --- | --- | ---: | --- | ---: |
| central-address | ready | ready | 326 | True / True | 0.5992 |
| neighbouring-address | ready | ready | 4 | True / True | 0.578 |
| street-3 | ready | ready | 5130 | True / True | 0.6304 |
| street-4 | ready | ready | 7163 | True / True | 0.6734 |
| street-5 | ready | ready | 5245 | True / True | 0.7652 |
| street-6 | ready | ready | 7588 | True / True | 0.7782 |
| street-7 | ready | ready | 6600 | True / True | 0.6524 |
| street-8 | ready | ready | 12660 | True / True | 0.7431 |
| street-9 | ready | ready | 12698 | True / True | 0.8807 |
| street-10 | ready | ready | 29712 | True / True | 1.0465 |
| street-11 | ready | ready | 43224 | True / True | 1.08 |
| identical-endpoints | same_place | same_place | None | None / None | 0.2017 |
| outside-municipality | outside_coverage | outside_coverage | None | None / None | 0.1034 |
| invalid-latitude | rejected | rejected | None | None / None | 0.0 |
