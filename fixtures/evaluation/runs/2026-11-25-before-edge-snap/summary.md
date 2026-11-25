# Frozen municipal journey validation

Passed: 13/14.

Expected software outcomes for source-backed points, not independently verified physical routes or human usability results.

| Case | Expected | Actual | Network m | Path / optimality | Seconds |
| --- | --- | --- | ---: | --- | ---: |
| central-address | ready | ready | 336 | True / True | 0.6543 |
| neighbouring-address | ready | same_place | None | None / None | 0.097 |
| street-3 | ready | ready | 5130 | True / True | 0.5914 |
| street-4 | ready | ready | 7162 | True / True | 0.632 |
| street-5 | ready | ready | 5245 | True / True | 0.7351 |
| street-6 | ready | ready | 7588 | True / True | 0.8616 |
| street-7 | ready | ready | 6600 | True / True | 0.9622 |
| street-8 | ready | ready | 12660 | True / True | 1.0613 |
| street-9 | ready | ready | 12698 | True / True | 0.9475 |
| street-10 | ready | ready | 29712 | True / True | 1.2999 |
| street-11 | ready | ready | 43224 | True / True | 1.4588 |
| identical-endpoints | same_place | same_place | None | None / None | 0.1553 |
| outside-municipality | outside_coverage | outside_coverage | None | None / None | 0.0521 |
| invalid-latitude | rejected | rejected | None | None / None | 0.0 |
