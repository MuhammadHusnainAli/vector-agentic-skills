"""ISO 9001:2015 (+ Amd 1:2024) auditable requirements, paraphrased, shared by gap_template.py and gap_score.py.

Each row: (clause, title, requirement, docinfo, core)
  docinfo  "maintain" = a document is required, "retain" = a record is required, "" = none
  core     True for clauses whose total absence is a system breakdown (graded major when not met)
"""

CLAUSES = [
    ("4.1", "Context of the organization", "Determine internal and external issues relevant to purpose and strategic direction, including whether climate change is relevant; monitor and review them", "", False),
    ("4.2", "Interested parties", "Determine relevant interested parties and their requirements (which can include climate change requirements); monitor and review them", "", False),
    ("4.3", "Scope of the QMS", "Define scope with products/services and sites; justify any requirement determined not applicable", "maintain", True),
    ("4.4", "QMS and its processes", "Determine processes, inputs/outputs, sequence and interaction, criteria, resources, responsibilities, risks; keep documented information to support and evidence operation", "maintain+retain", True),
    ("5.1.1", "Leadership and commitment", "Top management takes accountability for QMS effectiveness, ensures policy/objectives fit strategy, integrates QMS into business processes, promotes process approach and risk-based thinking", "", False),
    ("5.1.2", "Customer focus", "Top management ensures customer and legal requirements are met, risks to conformity are addressed, focus on customer satisfaction is maintained", "", False),
    ("5.2.1", "Quality policy", "Policy is appropriate to purpose and context, gives a framework for objectives, commits to meeting requirements and to continual improvement", "maintain", True),
    ("5.2.2", "Communicating the policy", "Policy is available as documented information, communicated, understood and applied, available to interested parties as appropriate", "maintain", False),
    ("5.3", "Roles, responsibilities and authorities", "Assign and communicate responsibility for QMS conformity, process outputs, reporting on performance, customer focus and integrity during change", "", False),
    ("6.1", "Risks and opportunities", "Determine risks and opportunities from 4.1/4.2, plan proportionate actions, integrate them into processes and evaluate effectiveness", "", True),
    ("6.2", "Quality objectives", "Set measurable objectives at relevant functions and levels consistent with the policy; plan what, resources, who, when and how results are evaluated", "maintain", True),
    ("6.3", "Planning of changes", "Plan QMS changes considering purpose, consequences, integrity, resources and responsibilities", "", False),
    ("7.1.1", "Resources - general", "Determine and provide resources, considering existing internal capability and what is needed from external providers", "", False),
    ("7.1.2", "People", "Provide the persons needed to operate and control processes", "", False),
    ("7.1.3", "Infrastructure", "Determine, provide and maintain buildings, equipment, software, transport and ICT", "", False),
    ("7.1.4", "Process environment", "Determine, provide and maintain the social, psychological and physical environment needed", "", False),
    ("7.1.5", "Monitoring and measuring resources", "Ensure measuring resources are suitable and maintained; calibrate or verify at intervals against traceable standards, identify status, act when found out of tolerance", "retain", False),
    ("7.1.6", "Organizational knowledge", "Determine, maintain and make available the knowledge needed; consider how to acquire knowledge for changing needs", "", False),
    ("7.2", "Competence", "Determine competence, ensure people are competent by education, training or experience, act to close gaps and evaluate the actions", "retain", False),
    ("7.3", "Awareness", "People are aware of the policy, relevant objectives, their contribution and the implications of not conforming", "", False),
    ("7.4", "Communication", "Determine what, when, with whom, how and who communicates internally and externally", "", False),
    ("7.5", "Documented information", "Create, identify, format, review and approve documented information; control distribution, access, storage, changes, retention, disposition and external documents", "", True),
    ("8.1", "Operational planning and control", "Plan, implement and control processes: requirements, criteria, resources, documented information; control planned changes and outsourced processes", "maintain+retain", False),
    ("8.2.1", "Customer communication", "Communicate product information, enquiries, contracts, orders, feedback and complaints, customer property, contingencies", "", False),
    ("8.2.2", "Determining requirements", "Define product/service requirements including legal ones; ensure the organization can meet its claims", "", False),
    ("8.2.3", "Review of requirements", "Review requirements before committing to supply, resolve differences, confirm unstated requirements", "retain", False),
    ("8.2.4", "Changes to requirements", "Amend documented information and inform people when requirements change", "", False),
    ("8.3", "Design and development", "Plan design stages, inputs, controls (reviews, verification, validation), outputs and changes", "retain", False),
    ("8.4", "Externally provided processes, products and services", "Set criteria to evaluate, select, monitor and re-evaluate external providers; define controls and communicate requirements", "retain", True),
    ("8.5.1", "Control of production and service provision", "Controlled conditions: documented characteristics and results, measuring resources, monitoring at stages, infrastructure, competent people, validation of special processes, error prevention, release and delivery", "maintain", False),
    ("8.5.2", "Identification and traceability", "Identify outputs and their status; control unique identification when traceability is required", "retain", False),
    ("8.5.3", "Customer or external provider property", "Identify, verify, protect and safeguard property; report loss or damage to the owner", "retain", False),
    ("8.5.4", "Preservation", "Preserve outputs during production and delivery (identification, handling, contamination control, packaging, storage, transport, protection)", "", False),
    ("8.5.5", "Post-delivery activities", "Meet post-delivery requirements considering legal requirements, consequences, product life, customer requirements and feedback", "", False),
    ("8.5.6", "Control of changes", "Review and control production changes; record the review, who authorized and the actions", "retain", False),
    ("8.6", "Release of products and services", "Verify requirements are met before release; record evidence of conformity and traceability to the authorizing person", "retain", True),
    ("8.7", "Control of nonconforming outputs", "Identify and control nonconforming outputs (correction, segregation, return, inform customer, concession); record the nonconformity, actions, concessions and authority", "retain", True),
    ("9.1.1", "Monitoring, measurement, analysis and evaluation", "Determine what, methods, when to monitor and when to analyse; evaluate performance and effectiveness", "retain", False),
    ("9.1.2", "Customer satisfaction", "Monitor customers' perception of how needs and expectations are met; decide methods to obtain and review it", "", False),
    ("9.1.3", "Analysis and evaluation", "Analyse data to evaluate conformity, satisfaction, QMS performance, planning, risk actions, providers and improvement needs", "", False),
    ("9.2", "Internal audit", "Plan and run an audit programme at planned intervals, defined criteria and scope, objective auditors, report results, take corrections and corrective actions without undue delay", "retain", True),
    ("9.3", "Management review", "Top management reviews the QMS at planned intervals with the required inputs and decides on improvement, changes and resources", "retain", True),
    ("10.1", "Improvement - general", "Select opportunities for improvement to meet requirements and enhance satisfaction", "", False),
    ("10.2", "Nonconformity and corrective action", "React, evaluate need for action to eliminate causes, implement, review effectiveness, update risks and the QMS", "retain", True),
    ("10.3", "Continual improvement", "Continually improve suitability, adequacy and effectiveness, using analysis and management review outputs", "", False),
]

# Clauses an organization may declare not applicable (4.3): only where it does not affect
# its ability to ensure conformity of products/services. In practice 8.3 and parts of 7.1.5 and 8.5.
MAY_NOT_APPLY = {"7.1.5", "8.3", "8.5.3", "8.5.5"}

BY_CLAUSE = {row[0]: row for row in CLAUSES}
