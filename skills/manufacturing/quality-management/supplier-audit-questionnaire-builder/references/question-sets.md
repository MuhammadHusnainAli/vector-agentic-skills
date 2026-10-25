# Supplier Audit Question Sets

Read by `scripts/questionnaire.py`. Section heading format: `### <Section> | weight <n> | <types or all> | <min risk>`.
Question format: `- [KO] <question> | <evidence>` (`[KO]` = knockout: scoring 0 or 1 blocks approval).
Types: machining, electronics, chemical, distributor, service. Min risk: low (always asked), medium, high.

### Management system | weight 15 | all | low
- [KO] Is the site certified to ISO 9001 (or IATF 16949 / AS9100 / ISO 13485) by an accredited certification body? | Certificate, scope, expiry, accreditation mark
- Are quality objectives set and reviewed by top management? | Objectives, last management review minutes
- Is there an internal audit programme covering all processes, with findings closed? | Programme, last 2 reports
- Is there a named quality contact with authority to stop shipment? | Org chart

### Contract review and planning | weight 10 | all | medium
- Are customer drawings, specifications and revision levels reviewed before order acceptance? | Order review records
- Are special characteristics and customer-specific requirements flowed to production? | Router, control plan
- Is capacity checked before accepting orders and delivery dates? | Capacity plan

### Sub-tier supplier control | weight 10 | all | medium
- Are sub-tier suppliers selected and evaluated against defined criteria? | Approved supplier list, evaluations
- Are customer requirements (including special processes and approved sources) flowed down on purchase orders? | Sample POs
- Is incoming material verified (inspection or certificates) before use? | Receiving records, CoCs

### Process control | weight 20 | machining,electronics,chemical | low
- [KO] Are work instructions and control plans available and current at the point of use? | Station documents vs register
- Is first-piece / set-up approval done and recorded before each run? | First-off records
- Are special processes (heat treatment, plating, welding, soldering, sterilization) validated and monitored? | Validation reports, parameter records
- Is preventive maintenance planned and recorded for critical equipment? | PM plan, records
- Are key characteristics monitored with SPC and reacted to? | Control charts, reaction log

### Inspection, test and measurement | weight 15 | machining,electronics,chemical | low
- [KO] Are all gauges and test equipment calibrated and traceable to national standards? | Calibration register, labels
- Is final inspection performed and recorded before shipment? | Final inspection records
- Has MSA (Gage R&R) been done for gauges used on key characteristics? | MSA studies
- Can the site produce the inspection reports or CoCs the customer requires? | Sample report

### Nonconforming product and corrective action | weight 15 | all | low
- [KO] Is nonconforming product identified and segregated so it cannot be shipped? | Quarantine area, NCR log
- Are customers notified and concessions obtained before shipping deviating product? | Concession records
- Are root causes analysed (8D, 5 Why) and effectiveness verified? | Sample CAPAs
- Are customer complaints answered within the required time? | Complaint log, response times

### Traceability, storage and delivery | weight 10 | all | medium
- Can finished product be traced to material lots and process records? | Trace exercise
- Are storage conditions, shelf life and FIFO controlled? | Storage area, stock records
- Is packaging defined and adequate to protect the product? | Packaging specs
- Is on-time delivery measured and acted on? | OTD KPI

### Machining specifics | weight 5 | machining | high
- Are tool life and offsets controlled and recorded? | Tool life records
- Is material certification checked against the specification (grade, heat number)? | Mill certs vs spec
- Are burrs, chips and coolant contamination controlled before packing? | Cleaning instruction

### Electronics specifics | weight 5 | electronics | high
- Is ESD control implemented and verified (ANSI/ESD S20.20 or IEC 61340-5-1)? | ESD audits, wrist strap logs
- Are moisture-sensitive devices handled per J-STD-033 (floor life, baking)? | MSL log
- Are workmanship standards (IPC-A-610 class) defined and operators certified? | IPC certificates
- Is counterfeit-part avoidance in place for components (authorized sources)? | Purchasing records

### Chemical specifics | weight 5 | chemical | high
- Are batch records complete and reviewed before release? | Batch records
- Is a certificate of analysis issued per batch against the agreed specification? | CoA samples
- Are raw-material shelf life and storage conditions controlled? | Stock records
- Are change notifications (formulation, site, source) sent to customers in advance? | Change notification procedure

### Distributor specifics | weight 5 | distributor | low
- [KO] Is product bought only from the original manufacturer or its authorized channel? | Franchise agreements, purchase records
- Is traceability to the original manufacturer's lot maintained and stated on the CoC? | CoC samples
- Is there a counterfeit detection and reporting process (e.g. AS6081 for independent distributors)? | Procedure, reports

### Service specifics | weight 20 | service | low
- [KO] Are staff competence requirements defined and records kept? | Competence matrix, certificates
- Are service reports or job records completed and reviewed? | Sample job records
- Is customer property (equipment, data, sites) protected? | Procedure, incident log
