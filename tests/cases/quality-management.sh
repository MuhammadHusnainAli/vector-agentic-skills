# Quality management skill script cases. Syntax: see tests/run_tests.sh.

# ---- ISO 9001 QMS
t 'gap_template: csv worksheet' 0 '6.1,Risks and opportunities' \
  "$QM/iso-9001-gap-analyzer/scripts/gap_template.py"
t 'gap_template: markdown clause filter' 0 '| 9.2 | Internal audit |' \
  "$QM/iso-9001-gap-analyzer/scripts/gap_template.py" --clause 9 --markdown
t 'gap_template: unknown clause exits 2' 2 'no clause matches' \
  "$QM/iso-9001-gap-analyzer/scripts/gap_template.py" --clause 11
t 'gap_score: missing internal audit is major' 1 'GA001 [major] 9.2 Internal audit: not implemented' \
  "$QM/iso-9001-gap-analyzer/scripts/gap_score.py" "$FX/qm/gap_filled.csv"
t 'gap_score: invalid n/a exclusion' 1 'GA005 [error] 5.3 Roles' \
  "$QM/iso-9001-gap-analyzer/scripts/gap_score.py" "$FX/qm/gap_filled.csv"
t 'gap_score: readiness by section' 1 'By section:  4: 87.5%  5: 100%  6: 50%' \
  "$QM/iso-9001-gap-analyzer/scripts/gap_score.py" "$FX/qm/gap_filled.csv"
STDIN=$'foo,bar\n1,2\n' t 'gap_score: wrong columns exits 2' 2 "needs at least 'clause' and 'status'" \
  "$QM/iso-9001-gap-analyzer/scripts/gap_score.py" -
t 'manual_scaffold: process interaction table' 0 '| Machining | core | Production manager |' \
  "$QM/iso-9001-quality-manual-writer/scripts/manual_scaffold.py" "$FX/qm/manual_profile.json"
t 'manual_scaffold: exclusion justified in scope' 0 '- **8.3 Design and development** - All parts are made' \
  "$QM/iso-9001-quality-manual-writer/scripts/manual_scaffold.py" "$FX/qm/manual_profile.json"
STDIN='{"company":"X","exclusions":[{"clause":"9.2","justification":"we are too small to audit anything"}]}' \
  t 'manual_scaffold: invalid exclusion exits 1' 1 'clause 9.2 cannot be excluded' \
  "$QM/iso-9001-quality-manual-writer/scripts/manual_scaffold.py" -
t 'manual_check: 2008 design clause exclusion' 1 'QM002 [high] clause 7.3 declared not applicable; it cannot be excluded (7.3 was design' \
  "$QM/iso-9001-quality-manual-writer/scripts/manual_check.py" "$FX/qm/manual_legacy.md"
t 'manual_check: management representative leftover' 1 "QM006 [medium] 'management representative' was removed" \
  "$QM/iso-9001-quality-manual-writer/scripts/manual_check.py" "$FX/qm/manual_legacy.md"
t 'manual_check: missing file exits 2' 2 'error:' \
  "$QM/iso-9001-quality-manual-writer/scripts/manual_check.py" "$FX/qm/nope.md"
t 'policy_check: complete policy passes' 0 'meets 5.2.1' \
  "$QM/quality-policy-objectives-drafter/scripts/policy_check.py" "$FX/qm/policy_good.txt" --company "Acme Precision"
t 'policy_check: slogan policy misses commitments' 1 'PO002 [high] no commitment to continual improvement' \
  "$QM/quality-policy-objectives-drafter/scripts/policy_check.py" "$FX/qm/policy_weak.txt"
t 'policy_check: generic slogans' 1 'generic slogan(s): world-class, zero defects' \
  "$QM/quality-policy-objectives-drafter/scripts/policy_check.py" "$FX/qm/policy_weak.txt"
t 'objective_check: target worse than baseline' 1 'lower is better but target 8 is not below baseline 6' \
  "$QM/quality-policy-objectives-drafter/scripts/objective_check.py" "$FX/qm/objectives.csv" --today 2026-10-24
t 'objective_check: function without objective' 1 "OB009 [medium] function 'Sales' has no quality objective" \
  "$QM/quality-policy-objectives-drafter/scripts/objective_check.py" "$FX/qm/objectives.csv" --functions Production Sales
t 'objective_check: complete objective scores 7/7' 1 '[2] Reduce internal scrap  (Production)  SMART 7/7' \
  "$QM/quality-policy-objectives-drafter/scripts/objective_check.py" "$FX/qm/objectives.csv"
STDIN=$'kpi,target\nx,1\n' t 'objective_check: wrong columns exits 2' 2 "needs an 'objective' column" \
  "$QM/quality-policy-objectives-drafter/scripts/objective_check.py" -
t 'procedure_scaffold: raci from steps' 0 '| 2 |  | R | C |  |  |' \
  "$QM/qms-procedure-writer/scripts/procedure_scaffold.py" "$FX/qm/procedure_spec.json"
STDIN='{"title":"X","steps":[{"action":"Inspect parts"}]}' t 'procedure_scaffold: step without actor exits 1' 1 'need both' \
  "$QM/qms-procedure-writer/scripts/procedure_scaffold.py" -
t 'procedure_lint: passive step' 1 "PR003 [medium] line 7: passive step with no actor" \
  "$QM/qms-procedure-writer/scripts/procedure_lint.py" "$FX/qm/procedure_bad.md"
t 'procedure_lint: missing sections' 1 "PR001 [high] no 'responsibilities' section" \
  "$QM/qms-procedure-writer/scripts/procedure_lint.py" "$FX/qm/procedure_bad.md"
t 'procedure_lint: vague wording' 1 "PR002 [medium] line 9: vague 'promptly'" \
  "$QM/qms-procedure-writer/scripts/procedure_lint.py" "$FX/qm/procedure_bad.md"
t 'clause_lookup: sub-clause resolves to parent' 0 '8.3 Design and development of products and services' \
  "$QM/iso-9001-clause-explainer/scripts/clause_lookup.py" 8.3.4
t 'clause_lookup: family lists children' 0 '8.5.6 Control of changes' \
  "$QM/iso-9001-clause-explainer/scripts/clause_lookup.py" 8.5
t 'clause_lookup: keyword search' 0 '7.1.5 Monitoring and measuring resources' \
  "$QM/iso-9001-clause-explainer/scripts/clause_lookup.py" --search calibration
t 'clause_lookup: 2008 preventive action mapping' 0 'ISO 9001:2008 8.5.3 -> ISO 9001:2015 6.1' \
  "$QM/iso-9001-clause-explainer/scripts/clause_lookup.py" --from-2008 8.5.3
t 'clause_lookup: unknown clause exits 1' 1 'auditable clauses run from 4.1 to 10.3' \
  "$QM/iso-9001-clause-explainer/scripts/clause_lookup.py" 12.4
t 'numbering_scheme: design with areas' 0 'QP   Procedure             e.g. QP-PRD-001' \
  "$QM/document-control-system-designer/scripts/numbering_scheme.py" --types QM QP WI QF --areas PRD QA
t 'numbering_scheme: revision letter in id' 1 'INVALID    QF-007C (revision letter in the ID?)' \
  "$QM/document-control-system-designer/scripts/numbering_scheme.py" --types QP WI QF --check "$FX/qm/doc_ids.txt"
t 'numbering_scheme: next free number' 1 'next free  WI-015' \
  "$QM/document-control-system-designer/scripts/numbering_scheme.py" --types QP WI QF --check "$FX/qm/doc_ids.txt"
t 'numbering_scheme: bad code exits 2' 2 'codes must be 2-4 upper-case letters' \
  "$QM/document-control-system-designer/scripts/numbering_scheme.py" --types qp
t 'register_audit: two approved revisions' 1 'DC002 [high] QP-007: revisions C, D all approved' \
  "$QM/document-control-system-designer/scripts/register_audit.py" "$FX/qm/doc_register.csv" --today 2026-10-24
t 'register_audit: obsolete at point of use' 1 'DC004 [high] WI-010: obsolete but still at: Lathe 3 station' \
  "$QM/document-control-system-designer/scripts/register_audit.py" "$FX/qm/doc_register.csv" --today 2026-10-24
t 'register_audit: overdue review' 1 'DC005 [medium] QP-002: periodic review due 2026-03-01, 237 days overdue' \
  "$QM/document-control-system-designer/scripts/register_audit.py" "$FX/qm/doc_register.csv" --today 2026-10-24
t 'roadmap: 40-person plan' 0 'Certificate expected: 2027-09-27 (~11 months)' \
  "$QM/iso-9001-certification-roadmap-planner/scripts/roadmap.py" --start 2026-11-02 --employees 40
t 'roadmap: iaf md5 audit days' 0 'initial 9 (stage 1 + stage 2)' \
  "$QM/iso-9001-certification-roadmap-planner/scripts/roadmap.py" --start 2026-11-02 --employees 180
t 'roadmap: unachievable target exits 1' 1 'NOT achievable - 19 days short' \
  "$QM/iso-9001-certification-roadmap-planner/scripts/roadmap.py" --start 2026-11-02 --employees 180 --maturity partial --target 2027-06-30
t 'roadmap: zero employees exits 2' 2 'must be at least 1' \
  "$QM/iso-9001-certification-roadmap-planner/scripts/roadmap.py" --start 2026-11-02 --employees 0

# ---- Auditing
t 'audit_schedule: high risk audited every 4 months after major' 1 '2027-05  Purchasing                    high    8.4                   A. Khan' \
  "$QM/internal-audit-schedule-planner/scripts/audit_schedule.py" "$FX/qm/audit_processes.csv" --start 2027-01 --auditors "$FX/qm/auditors.csv" --biennial-low
t 'audit_schedule: clause coverage gap' 1 'AS001 [high] clause 10 is not covered' \
  "$QM/internal-audit-schedule-planner/scripts/audit_schedule.py" "$FX/qm/audit_processes.csv" --start 2027-01
t 'audit_schedule: biennial low-risk deferred' 1 '(every 2 years: next cycle)' \
  "$QM/internal-audit-schedule-planner/scripts/audit_schedule.py" "$FX/qm/audit_processes.csv" --start 2027-01 --biennial-low
t 'audit_schedule: bad start exits 2' 2 'error:' \
  "$QM/internal-audit-schedule-planner/scripts/audit_schedule.py" "$FX/qm/audit_processes.csv" --start 2027-13
t 'checklist: purchasing with turtle' 0 '| 1 | Inputs | What triggers this process' \
  "$QM/iso-audit-checklist-generator/scripts/checklist.py" --process purchasing --turtle
t 'checklist: purchasing includes PO question' 0 'does it state the drawing revision' \
  "$QM/iso-audit-checklist-generator/scripts/checklist.py" --process purchasing
t 'checklist: clause family csv' 0 '8.5.6,Control of changes' \
  "$QM/iso-audit-checklist-generator/scripts/checklist.py" --clauses 8.5 --csv
t 'checklist: unknown process exits 2' 2 "unknown process 'painting'" \
  "$QM/iso-audit-checklist-generator/scripts/checklist.py" --process painting
t 'finding_lint: well-formed minor passes' 1 'NC-01 (minor): ok' \
  "$QM/qms-audit-finding-writer/scripts/finding_lint.py" "$FX/qm/findings.json"
t 'finding_lint: total absence graded minor' 1 "AF007 [medium] graded minor but describes a total absence ('No internal audits')" \
  "$QM/qms-audit-finding-writer/scripts/finding_lint.py" "$FX/qm/findings.json"
t 'finding_lint: advice graded as nc' 1 "AF003 [high] worded as advice ('could be improved')" \
  "$QM/qms-audit-finding-writer/scripts/finding_lint.py" "$FX/qm/findings.json"
t 'finding_lint: named person' 1 "AF005 [medium] names a person ('Mr. Smith')" \
  "$QM/qms-audit-finding-writer/scripts/finding_lint.py" "$FX/qm/findings.json"
STDIN='{"id":1}' t 'finding_lint: non-list exits 2' 2 'error:' \
  "$QM/qms-audit-finding-writer/scripts/finding_lint.py" -
t 'questionnaire: electronics high risk specifics' 0 'Is ESD control implemented and verified' \
  "$QM/supplier-audit-questionnaire-builder/scripts/questionnaire.py" --type electronics --risk high
t 'questionnaire: csv with knockout column' 0 '1.1,Management system,42.9,yes' \
  "$QM/supplier-audit-questionnaire-builder/scripts/questionnaire.py" --type distributor --risk low --csv
t 'score_questionnaire: knockout blocks approval' 1 'Decision: NOT APPROVED (knockout)' \
  "$QM/supplier-audit-questionnaire-builder/scripts/score_questionnaire.py" "$FX/qm/supplier_sa.csv"
t 'score_questionnaire: approved' 0 'Decision: APPROVED' \
  "$QM/supplier-audit-questionnaire-builder/scripts/score_questionnaire.py" "$FX/qm/supplier_sa_ok.csv"
STDIN=$'id,score\n1,3\n' t 'score_questionnaire: missing columns exits 2' 2 'CSV needs columns' \
  "$QM/supplier-audit-questionnaire-builder/scripts/score_questionnaire.py" -
t 'lpa_plan: rotation without collisions' 0 'W1    Mon Press             Tue Weld              Wed Assembly' \
  "$QM/layered-process-audit-designer/scripts/lpa_plan.py" --people "$FX/qm/lpa_people.csv" --weeks 4
t 'lpa_plan: workload per person' 0 'S. Patel                   100' \
  "$QM/layered-process-audit-designer/scripts/lpa_plan.py" --people "$FX/qm/lpa_people.csv" --weeks 4
t 'lpa_results: repeat failure escalates' 1 'LR001 [high] Q2 failed 5 times in Weld' \
  "$QM/layered-process-audit-designer/scripts/lpa_results.py" "$FX/qm/lpa_results.csv"
t 'lpa_results: layer gap' 1 'LR003 [medium] Press: layer 1 finds 100% compliance, higher layers 80%' \
  "$QM/layered-process-audit-designer/scripts/lpa_results.py" "$FX/qm/lpa_results.csv"
t 'lpa_results: stale question' 1 'LR004 [low] Q1: passed all 75 times' \
  "$QM/layered-process-audit-designer/scripts/lpa_results.py" "$FX/qm/lpa_results.csv"
t 'report_build: conclusion from minor findings' 0 'generally effective within the audit scope, with 1 minor nonconformity' \
  "$QM/audit-report-writer/scripts/report_build.py" "$FX/qm/audit_record.json"
t 'report_build: finding detail' 0 '### NC-01 - MINOR - 7.1.5.2' \
  "$QM/audit-report-writer/scripts/report_build.py" "$FX/qm/audit_record.json"
STDIN='{"findings":[{"id":"X","grade":"major"}]}' t 'report_build: incomplete report exits 1' 1 "RP001 [high] report lacks 'scope'" \
  "$QM/audit-report-writer/scripts/report_build.py" -
STDIN='[1]' t 'report_build: non-object exits 2' 2 'must be an object' \
  "$QM/audit-report-writer/scripts/report_build.py" -

# ---- Nonconformance and CAPA
t 'ncr_check: complete ncr' 1 'NCR-2611: complete' \
  "$QM/ncr-nonconformance-report-writer/scripts/ncr_check.py" "$FX/qm/ncrs.json"
t 'ncr_check: use-as-is without concession' 1 'NR004 [high] use-as-is needs a concession' \
  "$QM/ncr-nonconformance-report-writer/scripts/ncr_check.py" "$FX/qm/ncrs.json"
t 'ncr_check: customer escape containment gaps' 1 'NR003 [high] detected at customer: containment does not cover wip, transit, customer' \
  "$QM/ncr-nonconformance-report-writer/scripts/ncr_check.py" "$FX/qm/ncrs.json"
STDIN='not json' t 'ncr_check: bad json exits 2' 2 'error:' \
  "$QM/ncr-nonconformance-report-writer/scripts/ncr_check.py" -
t 'ncr_trend: repeat part and defect' 1 'NT001 [high] VB-2210 / bore oversize: 3 NCRs' \
  "$QM/ncr-nonconformance-report-writer/scripts/ncr_trend.py" "$FX/qm/ncr_log.csv" --today 2026-10-24
t 'ncr_trend: cost pareto by part' 1 'HS-110                            1935  46.1%   46.1%' \
  "$QM/ncr-nonconformance-report-writer/scripts/ncr_trend.py" "$FX/qm/ncr_log.csv" --today 2026-10-24 --by part --weight cost
t 'ncr_trend: escape rate' 1 'NT003 [medium] escape rate 20.0% > 10%' \
  "$QM/ncr-nonconformance-report-writer/scripts/ncr_trend.py" "$FX/qm/ncr_log.csv" --today 2026-10-24
t 'capa_check: strong plan passes' 0 'Plan meets 10.2 and uses strong actions.' \
  "$QM/capa-plan-writer/scripts/capa_check.py" "$FX/qm/capa_good.json"
t 'capa_check: operator error root cause' 1 "CP001 [high] RC1 'Operator error - not careful when packing' blames a person" \
  "$QM/capa-plan-writer/scripts/capa_check.py" "$FX/qm/capa_weak.json"
t 'capa_check: training-only actions' 1 'CP004 [medium] strongest action is training/reminder' \
  "$QM/capa-plan-writer/scripts/capa_check.py" "$FX/qm/capa_weak.json"
t 'capa_check: action strength ranking' 0 '[4] error-proof       Set tool life counter' \
  "$QM/capa-plan-writer/scripts/capa_check.py" "$FX/qm/capa_good.json"
t 'capa_aging: overdue capa' 1 'CA001 [high] CA-119 (Buyer): 24 days overdue in root-cause' \
  "$QM/capa-plan-writer/scripts/capa_aging.py" "$FX/qm/capa_log.csv" --today 2026-10-24
t 'capa_aging: closed too fast' 1 'CA003 [low] CA-112: closed 8 days after opening' \
  "$QM/capa-plan-writer/scripts/capa_aging.py" "$FX/qm/capa_log.csv" --today 2026-10-24
t 'eightd_check: complete 8d' 0 'D1 ok  D2 ok  D3 ok  D4 ok  D5 ok  D6 ok  D7 ok  D8 ok' \
  "$QM/8d-problem-solving-report-writer/scripts/eightd_check.py" "$FX/qm/8d_good.json"
t 'eightd_check: missing escape cause' 1 'D4: no escape root cause (why was it not detected?)' \
  "$QM/8d-problem-solving-report-writer/scripts/eightd_check.py" "$FX/qm/8d_weak.json"
t 'eightd_check: late containment' 1 'D3: containment 5 days after opening (expected within 24 h)' \
  "$QM/8d-problem-solving-report-writer/scripts/eightd_check.py" "$FX/qm/8d_weak.json"
t 'eightd_check: cause in problem statement' 1 'D2: the problem statement contains a cause' \
  "$QM/8d-problem-solving-report-writer/scripts/eightd_check.py" "$FX/qm/8d_weak.json"
t 'whys_check: good two-leg analysis' 0 'Chains reach controllable causes' \
  "$QM/five-whys-analysis-facilitator/scripts/whys_check.py" "$FX/qm/whys_good.txt"
t 'whys_check: therefore test printed' 0 '[Escape]' \
  "$QM/five-whys-analysis-facilitator/scripts/whys_check.py" "$FX/qm/whys_good.txt"
t 'whys_check: blame ending' 1 "WY002 [high] Chain: ends in blame ('The operator forgot" \
  "$QM/five-whys-analysis-facilitator/scripts/whys_check.py" "$FX/qm/whys_weak.txt"
t 'whys_check: circular answer' 1 'WY004 [medium] Chain why 2 repeats why 1' \
  "$QM/five-whys-analysis-facilitator/scripts/whys_check.py" "$FX/qm/whys_weak.txt"
STDIN='Problem: x' t 'whys_check: no why lines exits 2' 2 "no 'Why:' lines found" \
  "$QM/five-whys-analysis-facilitator/scripts/whys_check.py" -
t 'fishbone: verified cause listed first' 1 '[V] Method: Open trays with no dividers on line 2  - Transport trial' \
  "$QM/quality-fishbone-diagram-builder/scripts/fishbone.py" "$FX/qm/fishbone.csv" --problem "Scratches on HS-110 face A"
t 'fishbone: solution as cause' 1 "FB002 [medium] Method: 'Need a vision system' is a solution" \
  "$QM/quality-fishbone-diagram-builder/scripts/fishbone.py" "$FX/qm/fishbone.csv"
t 'fishbone: empty bone' 1 'FB001 [medium] Environment bone is empty' \
  "$QM/quality-fishbone-diagram-builder/scripts/fishbone.py" "$FX/qm/fishbone.csv"
t 'fishbone: mermaid output' 1 'b0["Man"] --> head' \
  "$QM/quality-fishbone-diagram-builder/scripts/fishbone.py" "$FX/qm/fishbone.csv" --format mermaid
t 'effectiveness: significant reduction is effective' 0 'one-sided p-value (after < before): 0.0035' \
  "$QM/capa-effectiveness-checker/scripts/effectiveness.py" rate --before 12 --before-units 4000 --after 1 --after-units 3500
t 'effectiveness: not yet demonstrated' 1 'Verdict: NOT YET DEMONSTRATED' \
  "$QM/capa-effectiveness-checker/scripts/effectiveness.py" rate --before 6 --before-units 2000 --after 2 --after-units 1500
t 'effectiveness: rate went up' 1 'Verdict: NOT EFFECTIVE' \
  "$QM/capa-effectiveness-checker/scripts/effectiveness.py" rate --before 2 --before-units 2000 --after 5 --after-units 2000
t 'effectiveness: zero-defect sample size' 1 '2995 consecutive units with zero defects' \
  "$QM/capa-effectiveness-checker/scripts/effectiveness.py" zero --target 0.001 --confidence 0.95 --so-far 1200
t 'effectiveness: clopper-pearson bound' 0 '95% upper bound 998 ppm' \
  "$QM/capa-effectiveness-checker/scripts/effectiveness.py" upper --defects 0 --units 3000 --target 0.001
t 'effectiveness: bad target exits 2' 2 'must be between 0 and 1' \
  "$QM/capa-effectiveness-checker/scripts/effectiveness.py" zero --target 2

# ---- Automotive and aerospace quality
t 'iatf_gap: template with csr rows' 0 'CSR:Ford,Ford customer-specific requirements' \
  "$QM/iatf-16949-requirement-checker/scripts/iatf_gap.py" --template --customers Ford
t 'iatf_gap: missing documented process is major' 1 'IG001 [major] 6.1.2.3 Contingency plans: required documented process missing' \
  "$QM/iatf-16949-requirement-checker/scripts/iatf_gap.py" "$FX/qm/iatf_filled.csv"
t 'iatf_gap: partial csr is major' 1 'IG002 [major] CSR:Stellantis' \
  "$QM/iatf-16949-requirement-checker/scripts/iatf_gap.py" "$FX/qm/iatf_filled.csv"
t 'iatf_gap: list documented processes' 0 '26 documented processes' \
  "$QM/iatf-16949-requirement-checker/scripts/iatf_gap.py" --list-processes
t 'iatf_gap: no arguments exits 2' 2 'usage' \
  "$QM/iatf-16949-requirement-checker/scripts/iatf_gap.py"
t 'apqp_plan: back-scheduled ppap gate' 0 'Product and process validation            2027-05-31  2027-08-09  PPAP approved' \
  "$QM/apqp-phase-planner/scripts/apqp_plan.py" --sop 2027-09-06 --complexity medium --today 2026-10-26
t 'apqp_plan: compressed timeline' 1 'COMPRESSED: phase 1 should have started' \
  "$QM/apqp-phase-planner/scripts/apqp_plan.py" --sop 2027-03-01 --complexity high --today 2026-10-26
t 'apqp_plan: late deliverable' 1 "LATE  phase 1 'Preliminary special characteristics' is in-progress" \
  "$QM/apqp-phase-planner/scripts/apqp_plan.py" --sop 2027-09-06 --status "$FX/qm/apqp_status.csv" --today 2027-03-01
t 'apqp_plan: bad date exits 2' 2 'error' \
  "$QM/apqp-phase-planner/scripts/apqp_plan.py" --sop 2027-13-01
t 'ppap_package: level 3 missing submit items' 1 'Missing, must be SUBMITTED: 3 Customer engineering approval' \
  "$QM/ppap-submission-package-builder/scripts/ppap_package.py" --level 3 --have "$FX/qm/ppap_have.txt" --no-appearance
t 'ppap_package: level 1 psw only' 0 '18  Part submission warrant (PSW)             submit' \
  "$QM/ppap-submission-package-builder/scripts/ppap_package.py" --level 1
t 'ppap_package: level 2 retains pfmea' 0 ' 6  Process FMEA                              retain' \
  "$QM/ppap-submission-package-builder/scripts/ppap_package.py" --level 2
t 'psw_check: marginal ppk needs customer approval' 0 'index 1.41 between 1.33 and 1.67' \
  "$QM/ppap-submission-package-builder/scripts/psw_check.py" "$FX/qm/psw.json"
STDIN='{"part_number":"X","results":{"dimensional":false}}' t 'psw_check: failed results block signing' 1 'Do not sign yet.' \
  "$QM/ppap-submission-package-builder/scripts/psw_check.py" -
t 'as9100_gap: counterfeit control missing is major' 1 'AG001 [major] 8.1.4 Prevention of counterfeit parts' \
  "$QM/as9100-gap-analyzer/scripts/as9100_gap.py" "$FX/qm/as9100_filled.csv"
t 'as9100_gap: management representative cannot be n/a' 1 'AG005 [error] 5.3 Management representative' \
  "$QM/as9100-gap-analyzer/scripts/as9100_gap.py" "$FX/qm/as9100_filled.csv"
t 'as9100_gap: template marks core rows' 0 '8.5.1.3,Production process verification (FAI)' \
  "$QM/as9100-gap-analyzer/scripts/as9100_gap.py" --template
t 'pfmea_ap: AP H without action' 1 'FM001 [high] row 5 OP45 Crimp / Low pull-out force / Crimp height drift: AP H (S9 O5 D6)' \
  "$QM/process-fmea-builder/scripts/pfmea_ap.py" "$FX/qm/pfmea.csv"
t 'pfmea_ap: severity 10 low occurrence is L' 1 'L   10  3  2   60  OP40 Weld' \
  "$QM/process-fmea-builder/scripts/pfmea_ap.py" "$FX/qm/pfmea.csv"
t 'pfmea_ap: visual inspection rated D2' 1 "FM004 [medium] row 4 OP40 Weld / Weld crack / Weld current too low: D2 claimed for 'Visual inspection'" \
  "$QM/process-fmea-builder/scripts/pfmea_ap.py" "$FX/qm/pfmea.csv"
t 'pfmea_ap: out of range rating' 1 'FM003 [high] row 7 OP60 Wash' \
  "$QM/process-fmea-builder/scripts/pfmea_ap.py" "$FX/qm/pfmea.csv"
t 'pfmea_ap: csv adds AP column' 1 'OP45 Crimp,Crimp terminal,Low pull-out force' \
  "$QM/process-fmea-builder/scripts/pfmea_ap.py" "$FX/qm/pfmea.csv" --csv
t 'cp_from_pfmea: parses sampling frequency' 0 'Bore gauge 1 in 50,1,every 50 parts' \
  "$QM/control-plan-writer/scripts/cp_from_pfmea.py" "$FX/qm/pfmea.csv" --part VB-2210
t 'cp_from_pfmea: error-proofing control method' 0 'Thread presence sensor (automatic),100%,continuous,Error-proofing' \
  "$QM/control-plan-writer/scripts/cp_from_pfmea.py" "$FX/qm/pfmea.csv"
t 'cp_check: weak control on CC' 1 "CPL005 [high] OP45 #4 Pull-out force: CC needs SPC" \
  "$QM/control-plan-writer/scripts/cp_check.py" "$FX/qm/control_plan.csv"
t 'cp_check: reaction plan without containment' 1 'CPL006 [medium] OP45 #4 Pull-out force' \
  "$QM/control-plan-writer/scripts/cp_check.py" "$FX/qm/control_plan.csv"
t 'cp_check: pfmea cross-check' 1 "CPL007 [medium] PFMEA OP45 Crimp: control 'Crimp height check at setup' from the PFMEA" \
  "$QM/control-plan-writer/scripts/cp_check.py" "$FX/qm/control_plan.csv" --pfmea "$FX/qm/pfmea.csv"

# ---- Statistical quality control
t 'control_limits: xbar-r selected for n=5' 1 'Chart: XBAR-R  (25 subgroups, n = 5)' \
  "$QM/manufacturing-spc-chart-builder/scripts/control_limits.py" "$FX/qm/bore.csv" --value diameter --subgroup hour
t 'control_limits: shifted subgroup beyond limits' 1 'beyond limits at: 17' \
  "$QM/manufacturing-spc-chart-builder/scripts/control_limits.py" "$FX/qm/bore.csv" --value diameter --subgroup hour
t 'control_limits: phase I exclusion' 0 'Recomputed without out-of-control subgroups: 17' \
  "$QM/manufacturing-spc-chart-builder/scripts/control_limits.py" "$FX/qm/bore.csv" --value diameter --subgroup hour --exclude-ooc
t 'control_limits: p chart for varying n' 1 'Chart: P  (25 points)' \
  "$QM/manufacturing-spc-chart-builder/scripts/control_limits.py" "$FX/qm/rejects.csv" --defectives rejects --n inspected
t 'control_limits: attribute without n exits 2' 2 'attribute charts need --n' \
  "$QM/manufacturing-spc-chart-builder/scripts/control_limits.py" "$FX/qm/rejects.csv" --defectives rejects
t 'plot_chart: svg with spec lines' 0 'USL 12.018' \
  "$QM/manufacturing-spc-chart-builder/scripts/plot_chart.py" "$FX/qm/bore.csv" --value diameter --subgroup hour --usl 12.018 --lsl 12.000
t 'capability: cpk with confidence interval' 0 'Cpk   1.35   (95% CI 1.17 to 1.53)' \
  "$QM/manufacturing-cpk-capability-calculator/scripts/capability.py" "$FX/qm/bore.csv" --value diameter --lsl 12.000 --usl 12.018 --subgroup hour
t 'capability: ppk below cpk warns about drift' 0 'Ppk well below Cpk' \
  "$QM/manufacturing-cpk-capability-calculator/scripts/capability.py" "$FX/qm/bore.csv" --value diameter --lsl 12.000 --usl 12.018 --subgroup hour
t 'capability: skewed data fails normality' 1 '-> NOT normal' \
  "$QM/manufacturing-cpk-capability-calculator/scripts/capability.py" "$FX/qm/flatness.csv" --value flatness --usl 0.05
t 'capability: percentile method' 1 'Ppk (percentile) 1.23 vs required 1.33' \
  "$QM/manufacturing-cpk-capability-calculator/scripts/capability.py" "$FX/qm/flatness.csv" --value flatness --usl 0.05 --method percentile
t 'capability: no spec exits 2' 2 'give --lsl and/or --usl' \
  "$QM/manufacturing-cpk-capability-calculator/scripts/capability.py" "$FX/qm/bore.csv" --value diameter
t 'gage_rr_anova: interaction pooled' 1 'p = 0.314 -> pooled into repeatability' \
  "$QM/gage-rr-msa-analyzer/scripts/gage_rr_anova.py" "$FX/qm/grr.csv" --tolerance 0.018
t 'gage_rr_anova: conditional verdict' 1 'Verdict on %Tolerance 18.4% and ndc 13: CONDITIONALLY ACCEPTABLE' \
  "$QM/gage-rr-msa-analyzer/scripts/gage_rr_anova.py" "$FX/qm/grr.csv" --tolerance 0.018
t 'gage_rr_anova: acceptable on study variation for wide tolerance' 0 'ACCEPTABLE' \
  "$QM/gage-rr-msa-analyzer/scripts/gage_rr_anova.py" "$FX/qm/grr.csv" --tolerance 0.05
t 'gage_rr_xbar_r: worksheet grr' 1 'GRR               0.0005283   10.5%       17.6%' \
  "$QM/gage-rr-msa-analyzer/scripts/gage_rr_xbar_r.py" "$FX/qm/grr.csv" --tolerance 0.018
t 'attribute_agreement: poor appraiser' 1 'Cleo             75%        78%  25.0%' \
  "$QM/gage-rr-msa-analyzer/scripts/attribute_agreement.py" "$FX/qm/attribute.csv"
t 'attribute_agreement: unknown bad label exits 2' 2 "--bad 'NOK' is not one of the labels" \
  "$QM/gage-rr-msa-analyzer/scripts/attribute_agreement.py" "$FX/qm/attribute.csv" --bad NOK
t 'z14_plan: lot 1000 aql 1.0' 0 'n = 80, Ac = 2, Re = 3' \
  "$QM/acceptance-sampling-plan-selector/scripts/z14_plan.py" --lot 1000 --aql 1.0
t 'z14_plan: arrow changes sample size' 0 'Table II-A arrow (down) -> use the plan for code letter H' \
  "$QM/acceptance-sampling-plan-selector/scripts/z14_plan.py" --lot 200 --aql 1.0
t 'z14_plan: sample exceeds lot' 0 'inspect 100% of the lot' \
  "$QM/acceptance-sampling-plan-selector/scripts/z14_plan.py" --lot 10 --aql 0.65
t 'z14_plan: non-preferred aql exits 2' 2 'is not a preferred value' \
  "$QM/acceptance-sampling-plan-selector/scripts/z14_plan.py" --lot 1000 --aql 2.0
t 'oc_curve: aoql with lot size' 0 'AOQL (worst average outgoing quality with rejected lots 100% sorted): 1.582%' \
  "$QM/acceptance-sampling-plan-selector/scripts/oc_curve.py" oc --n 80 --c 2 --lot 1000
t 'oc_curve: design from risks' 0 'Plan: n = 132, c = 3' \
  "$QM/acceptance-sampling-plan-selector/scripts/oc_curve.py" design --aql 0.01 --ltpd 0.05
t 'oc_curve: c0 plan' 0 'c = 0 plan: n = 45' \
  "$QM/acceptance-sampling-plan-selector/scripts/oc_curve.py" c0 --ltpd 0.05
t 'we_rules: sustained shift merged into one signal' 1 'WE4 at 22 (points 15-24)' \
  "$QM/western-electric-rules-checker/scripts/we_rules.py" "$FX/qm/run_rules.csv" --value x --center 50 --sigma 1
t 'we_rules: single point beyond 3 sigma' 1 'WE1 at 31 (point 31)' \
  "$QM/western-electric-rules-checker/scripts/we_rules.py" "$FX/qm/run_rules.csv" --value x --center 50 --sigma 1
t 'we_rules: nelson trend rule' 1 'N3 at 45 (points 40-47)' \
  "$QM/western-electric-rules-checker/scripts/we_rules.py" "$FX/qm/run_rules.csv" --value x --center 50 --sigma 1 --nelson
STDIN=$'x\n1\n2\n' t 'we_rules: too few points exits 2' 2 'need at least 8 points' \
  "$QM/western-electric-rules-checker/scripts/we_rules.py" /dev/stdin --value x
t 'pareto: vital few by count' 0 'Vital few (* up to 80%): burr, scratch, oversize bore, porosity = 4 of 9 categories' \
  "$QM/pareto-defect-analyzer/scripts/pareto.py" "$FX/qm/defects.csv" --count qty --cost unit_cost
t 'pareto: count and cost disagree' 0 "PA003 top by count is 'burr' but top by cost is 'oversize bore'" \
  "$QM/pareto-defect-analyzer/scripts/pareto.py" "$FX/qm/defects.csv" --count qty --cost unit_cost
t 'pareto: stratified by line' 0 'line L2: total 437; top scratch 41%' \
  "$QM/pareto-defect-analyzer/scripts/pareto.py" "$FX/qm/defects.csv" --count qty --by line
t 'pareto: before after comparison' 0 'burr                                    46          12     -74%' \
  "$QM/pareto-defect-analyzer/scripts/pareto.py" "$FX/qm/defects.csv" --period month --compare 2026-08 2026-10
t 'pareto: svg chart' 0 '<polyline points=' \
  "$QM/pareto-defect-analyzer/scripts/pareto.py" "$FX/qm/defects.csv" --svg
t 'pareto: cost weight without cost exits 2' 2 '--weight cost needs --cost' \
  "$QM/pareto-defect-analyzer/scripts/pareto.py" "$FX/qm/defects.csv" --weight cost

# ---- Six Sigma
t 'charter_check: good charter passes' 0 "Charter is ready for the champion's sign-off." \
  "$QM/manufacturing-dmaic-charter-writer/scripts/charter_check.py" "$FX/qm/charter_good.json"
t 'charter_check: cause in problem statement' 1 "CH001 [high] problem statement contains 'because'" \
  "$QM/manufacturing-dmaic-charter-writer/scripts/charter_check.py" "$FX/qm/charter_weak.json"
t 'charter_check: target worse than baseline' 1 'CH004 [high] target 3.5 is not better than baseline 3.1' \
  "$QM/manufacturing-dmaic-charter-writer/scripts/charter_check.py" "$FX/qm/charter_weak.json"
t 'copq: savings and payback' 0 'payback 3.8 months' \
  "$QM/manufacturing-dmaic-charter-writer/scripts/copq.py" --units 240000 --defect-rate 0.031 --scrap-share 0.6 --scrap-cost 9.50 --rework-cost 3.20 --escape-share 0.02 --external-cost 85 --appraisal 12000 --target-rate 0.008 --project-cost 15000
t 'copq: ppm input' 0 '125 defects per year' \
  "$QM/manufacturing-dmaic-charter-writer/scripts/copq.py" --units 50000 --defect-rate 2500ppm --scrap-cost 40
t 'copq: bad rate exits 2' 2 'rate must be a fraction' \
  "$QM/manufacturing-dmaic-charter-writer/scripts/copq.py" --units 100 --defect-rate 5
t 'dpmo: dpmo and sigma' 0 'Sigma level = 4.34 (short-term, 1.5 shift)' \
  "$QM/six-sigma-dpmo-calculator/scripts/dpmo.py" dpmo --defects 38 --units 1200 --opportunities 14
t 'dpmo: six sigma is 3.4 dpmo' 0 'sigma level 6.00' \
  "$QM/six-sigma-dpmo-calculator/scripts/dpmo.py" sigma --dpmo 3.4
t 'dpmo: rolled throughput yield' 0 'Rolled throughput yield = 89.86%' \
  "$QM/six-sigma-dpmo-calculator/scripts/dpmo.py" rty --yields 0.98 0.95 0.995 0.97
t 'dpmo: rty from steps csv' 0 'worst step: Deburr' \
  "$QM/six-sigma-dpmo-calculator/scripts/dpmo.py" rty --steps "$FX/qm/rty_steps.csv"
t 'dpmo: bad units exits 2' 2 'need units > 0' \
  "$QM/six-sigma-dpmo-calculator/scripts/dpmo.py" dpmo --defects 1 --units 0 --opportunities 3
t 'doe_design: half fraction resolution IV' 0 'Defining relation: I = ABCD   Resolution IV' \
  "$QM/design-of-experiments-planner/scripts/doe_design.py" --factors Speed:800:1200 Feed:0.10:0.20 Insert:A:B Coolant:5:8 --fraction 1
t 'doe_design: max runs picks 2^7-3' 0 'Design: 2^7-3 = 16 runs' \
  "$QM/design-of-experiments-planner/scripts/doe_design.py" --factors A:1:2 B:1:2 C:1:2 D:1:2 E:1:2 F:1:2 G:1:2 --max-runs 16
t 'doe_design: centre points need numeric levels' 2 'centre points need numeric levels' \
  "$QM/design-of-experiments-planner/scripts/doe_design.py" --factors Speed:800:1200 Insert:A:B --center 2
t 'doe_analyze: lenth finds interaction' 0 'Feed*Nose                             0.3954        -  *' \
  "$QM/design-of-experiments-planner/scripts/doe_analyze.py" "$FX/qm/doe_runs.csv" --goal min
t 'doe_analyze: recommended settings' 0 'Speed low, Feed low, Nose high' \
  "$QM/design-of-experiments-planner/scripts/doe_analyze.py" "$FX/qm/doe_runs.csv" --goal min
t 'pick_test: paired t' 0 'Recommended: Paired t-test' \
  "$QM/hypothesis-test-selector/scripts/pick_test.py" --y continuous --x 2-groups --paired
t 'pick_test: non-normal k groups' 0 'Recommended: Kruskal-Wallis' \
  "$QM/hypothesis-test-selector/scripts/pick_test.py" --y continuous --x k-groups --not-normal
t 'pick_test: proportions across groups' 0 'Chi-square test of association' \
  "$QM/hypothesis-test-selector/scripts/pick_test.py" --y proportion --x k-groups
t 'run_test: welch t significant' 1 'p = 0.006665 < alpha 0.05: significant - the means differ.' \
  "$QM/hypothesis-test-selector/scripts/run_test.py" t2 "$FX/qm/machines2.csv" --col diameter --group machine
t 'run_test: anova' 0 'One-way ANOVA: 3 groups, F = 2.495' \
  "$QM/hypothesis-test-selector/scripts/run_test.py" anova "$FX/qm/machines.csv" --col diameter --group machine
t 'run_test: paired improvement' 1 'mean difference = -0.2193333' \
  "$QM/hypothesis-test-selector/scripts/run_test.py" paired "$FX/qm/paired.csv" --a before --b after
t 'run_test: chi-square association' 1 'chi2 = 19.973, df = 2' \
  "$QM/hypothesis-test-selector/scripts/run_test.py" chi2 "$FX/qm/shift_defects.csv"
t 'run_test: two proportions not significant' 0 'p = 0.05513 >= alpha 0.05' \
  "$QM/hypothesis-test-selector/scripts/run_test.py" prop2 --x1 12 --n1 400 --x2 4 --n2 380
t 'run_test: t2 with three groups exits 2' 2 'need exactly 2 groups' \
  "$QM/hypothesis-test-selector/scripts/run_test.py" t2 "$FX/qm/machines.csv" --col diameter --group machine
t 'parse_minitab: capability drift warning' 1 'WARN    Ppk 1.14 well below Cpk 1.35' \
  "$QM/minitab-analysis-interpreter/scripts/parse_minitab.py" "$FX/qm/minitab/capability.txt"
t 'parse_minitab: gage conditional' 1 '%Tolerance 18.4% between 10 and 30%' \
  "$QM/minitab-analysis-interpreter/scripts/parse_minitab.py" "$FX/qm/minitab/gage.txt"
t 'parse_minitab: regression overfit' 1 'R-sq(pred) 71.2% is 16 points below R-sq' \
  "$QM/minitab-analysis-interpreter/scripts/parse_minitab.py" "$FX/qm/minitab/regression.txt"
t 'parse_minitab: t-test result' 0 'excludes 0: difference shown' \
  "$QM/minitab-analysis-interpreter/scripts/parse_minitab.py" "$FX/qm/minitab/ttest.txt"
STDIN='hello world' t 'parse_minitab: unrecognised exits 2' 2 'no recognised Minitab output' \
  "$QM/minitab-analysis-interpreter/scripts/parse_minitab.py" -
t 'quiz: domain list' 0 'Measure       6 questions' \
  "$QM/green-belt-exam-tutor/scripts/quiz.py" --list
t 'quiz: all correct passes' 0 'Score: 5/5 = 100%' \
  "$QM/green-belt-exam-tutor/scripts/quiz.py" --n 5 --seed 3 --answers DCACB
t 'quiz: wrong answers explained and fail' 1 'below pass mark' \
  "$QM/green-belt-exam-tutor/scripts/quiz.py" --n 5 --seed 3 --answers ADBDC
t 'quiz: wrong answer count exits 2' 2 'give 5 answers using A-D' \
  "$QM/green-belt-exam-tutor/scripts/quiz.py" --n 5 --seed 3 --answers AB

# ---- Supplier quality
t 'scorecard: grade D supplier' 1 'SC001 CastCorp: grade D (7)' \
  "$QM/supplier-quality-scorecard-builder/scripts/scorecard.py" "$FX/qm/supplier_perf.csv"
t 'scorecard: declining two periods' 1 'SC002 CastCorp: score fell two periods running (88 -> 56 -> 7)' \
  "$QM/supplier-quality-scorecard-builder/scripts/scorecard.py" "$FX/qm/supplier_perf.csv"
t 'scorecard: ppm above target without scar' 1 'SC003 PlastiForm: PPM 886 above target with no SCAR issued' \
  "$QM/supplier-quality-scorecard-builder/scripts/scorecard.py" "$FX/qm/supplier_perf.csv"
t 'scorecard: unknown period exits 2' 2 "period '2025-Q1' not in the data" \
  "$QM/supplier-quality-scorecard-builder/scripts/scorecard.py" "$FX/qm/supplier_perf.csv" --period 2025-Q1
t 'inspection_plan: skip-lot for proven supplier' 1 'skip-lot      1 lot in 4 at n=114, c=0' \
  "$QM/incoming-inspection-plan-writer/scripts/inspection_plan.py" "$FX/qm/incoming_parts.csv"
t 'inspection_plan: grade D critical is 100%' 1 'tightened     100%  (grade D supplier, critical characteristic)' \
  "$QM/incoming-inspection-plan-writer/scripts/inspection_plan.py" "$FX/qm/incoming_parts.csv"
t 'inspection_plan: grade D without scar' 1 'II001 [medium] CastCorp: grade D supplier' \
  "$QM/incoming-inspection-plan-writer/scripts/inspection_plan.py" "$FX/qm/incoming_parts.csv"
STDIN=$'part,characteristic,class\nX,Y,fatal\n' t 'inspection_plan: bad class exits 2' 2 "must be critical, major or minor" \
  "$QM/incoming-inspection-plan-writer/scripts/inspection_plan.py" /dev/stdin
t 'scar_check: weak response rejected' 1 'Supplier response: REJECT' \
  "$QM/supplier-corrective-action-request-writer/scripts/scar_check.py" "$FX/qm/scar_weak.json"
t 'scar_check: missing escape cause' 1 'SR102 [high] no escape root cause' \
  "$QM/supplier-corrective-action-request-writer/scripts/scar_check.py" "$FX/qm/scar_weak.json"
t 'scar_check: good response accepted' 0 'Supplier response: ACCEPT' \
  "$QM/supplier-corrective-action-request-writer/scripts/scar_check.py" "$FX/qm/scar_good.json"
STDIN='{"scar_id":"S1","problem":{"requirement":"x"},"issued":"2026-01-01","due":{"containment":"2026-01-10"}}' \
  t 'scar_check: incomplete request' 1 'Request incomplete: fix before sending.' \
  "$QM/supplier-corrective-action-request-writer/scripts/scar_check.py" -
t 'asl_audit: po outside approved scope' 1 "AL002 [high] PlastiForm: PO PO-9004: 'anodising' is outside the approved scope" \
  "$QM/approved-supplier-list-manager/scripts/asl_audit.py" "$FX/qm/asl.csv" --pos "$FX/qm/pos.csv" --today 2026-10-24
t 'asl_audit: off-list supplier' 1 'AL001 [high] QuickParts: PO PO-9005: supplier is not on the ASL' \
  "$QM/approved-supplier-list-manager/scripts/asl_audit.py" "$FX/qm/asl.csv" --pos "$FX/qm/pos.csv" --today 2026-10-24
t 'asl_audit: probation past end date' 0 'AL005 [medium] CastCorp: probation ended 2026-09-30' \
  "$QM/approved-supplier-list-manager/scripts/asl_audit.py" "$FX/qm/asl.csv" --today 2026-10-24
t 'asl_audit: expired certificate' 0 'AL003 [medium] PlastiForm: certificate (ISO 9001:2015) expired 2026-03-31' \
  "$QM/approved-supplier-list-manager/scripts/asl_audit.py" "$FX/qm/asl.csv" --today 2026-10-24
t 'dev_plan: priority and decisions' 0 'CastCorp             31.1%     52    high   67.15  DEVELOP' \
  "$QM/supplier-development-plan-writer/scripts/dev_plan.py" "$FX/qm/dev_suppliers.csv" --top 2 --start 2026-11-02
t 'dev_plan: replace small non-strategic supplier' 0 'Resource instead of developing: SmallParts' \
  "$QM/supplier-development-plan-writer/scripts/dev_plan.py" "$FX/qm/dev_suppliers.csv"
t 'dev_plan: lever for capability gap' 0 'day 45  capability: Capability studies' \
  "$QM/supplier-development-plan-writer/scripts/dev_plan.py" "$FX/qm/dev_suppliers.csv" --top 1 --start 2026-11-02
STDIN=$'name,spend\nX,1\n' t 'dev_plan: wrong columns exits 2' 2 'CSV needs supplier, spend and score' \
  "$QM/supplier-development-plan-writer/scripts/dev_plan.py" /dev/stdin
