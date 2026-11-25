# Frozen municipal journey validation

Passed: 14/14.

Expected software outcomes for source-backed points, not independently verified physical routes or human usability results.

| Case | Expected | Actual | Network m | Path / optimality | Seconds |
| --- | --- | --- | ---: | --- | ---: |
| central-address | ready | ready | 326 | True / True | 0.7625 |
| neighbouring-address | ready | ready | 4 | True / True | 0.7603 |
| street-3 | ready | ready | 5130 | True / True | 0.807 |
| street-4 | ready | ready | 7163 | True / True | 0.8914 |
| street-5 | ready | ready | 5245 | True / True | 0.9621 |
| street-6 | ready | ready | 7588 | True / True | 0.9986 |
| street-7 | ready | ready | 6600 | True / True | 0.8497 |
| street-8 | ready | ready | 12660 | True / True | 0.9975 |
| street-9 | ready | ready | 12698 | True / True | 1.1191 |
| street-10 | ready | ready | 29712 | True / True | 1.3426 |
| street-11 | ready | ready | 43224 | True / True | 1.4314 |
| identical-endpoints | same_place | same_place | None | None / None | 0.253 |
| outside-municipality | outside_coverage | outside_coverage | None | None / None | 0.1265 |
| invalid-latitude | rejected | rejected | None | None / None | 0.0 |
