# Green Belt Practice Question Bank

Original practice questions by domain, each with a worked explanation. `scripts/quiz.py` reads this file:
keep the `### <id> | <domain>` heading, options `- A)`..`- D)`, `Answer:` and `Why:` lines.

### F01 | Fundamentals
A process running at 3.4 defects per million opportunities is described as:
- A) 3 sigma
- B) 4.5 sigma short-term
- C) 6 sigma short-term (with the 1.5 sigma shift)
- D) 6 sigma long-term
Answer: C
Why: 3.4 DPMO is the long-term tail at 4.5 sigma; adding the conventional 1.5 shift gives 6 sigma short-term.

### F02 | Fundamentals
Producing more, or earlier, than the next process or customer needs is which waste?
- A) Inventory
- B) Overproduction
- C) Motion
- D) Over-processing
Answer: B
Why: Overproduction is making too much or too early; it creates inventory, which is a separate waste.

### F03 | Fundamentals
Available time is 27,000 s per shift and customer demand is 450 units per shift. What is the takt time?
- A) 45 s
- B) 60 s
- C) 75 s
- D) 600 s
Answer: B
Why: Takt = available time / demand = 27,000 / 450 = 60 s per unit.

### F04 | Fundamentals
Which role sponsors a project, selects it and removes organisational barriers?
- A) Champion
- B) Green belt
- C) Process owner
- D) Master black belt
Answer: A
Why: The champion (sponsor) owns the business case and removes barriers; the process owner sustains the gains.

### F05 | Fundamentals
Three steps have first-pass yields of 95%, 90% and 98%. What is the rolled throughput yield?
- A) 90.8%
- B) 83.8%
- C) 94.3%
- D) 98.0%
Answer: B
Why: RTY = 0.95 x 0.90 x 0.98 = 0.838. The average (94.3%) hides the hidden factory.

### F06 | Fundamentals
In the Kano model, a feature whose absence causes dissatisfaction but whose presence does not raise satisfaction is:
- A) Must-be (basic)
- B) Performance (one-dimensional)
- C) Attractive (delighter)
- D) Indifferent
Answer: A
Why: Basic requirements are expected; meeting them only avoids dissatisfaction.

### D01 | Define
A good problem statement contains:
- A) The root cause
- B) The proposed solution
- C) What, where, when and the magnitude of the gap
- D) The names of the team members
Answer: C
Why: The problem statement describes the measurable gap; causes come in Analyze and solutions in Improve.

### D02 | Define
In a SIPOC diagram, the "C" stands for:
- A) Controls
- B) Customers
- C) Costs
- D) CTQs
Answer: B
Why: Suppliers, Inputs, Process, Outputs, Customers.

### D03 | Define
A customer need translated into a measurable requirement with a specification is a:
- A) CTQ
- B) SIPOC
- C) RACI
- D) Gantt chart
Answer: A
Why: Critical-to-quality characteristics come from the voice of the customer via a CTQ tree.

### D04 | Define
Which tool is used to agree what is inside and outside the project scope?
- A) In-frame / out-of-frame
- B) Pareto chart
- C) Control chart
- D) Scatter plot
Answer: A
Why: In/out of frame (or scope statements) makes boundaries explicit before the project starts.

### D05 | Define
Which of these is a cost of poor quality?
- A) The annual training budget
- B) Scrap, rework and warranty claims
- C) Machine depreciation
- D) Design engineers' salaries
Answer: B
Why: COPQ covers internal failure (scrap, rework), external failure (warranty, returns) and appraisal.

### D06 | Define
An operational definition of the primary metric is needed so that:
- A) Everyone measures and counts it the same way
- B) The metric improves faster
- C) The project can skip Measure
- D) The champion can approve the charter
Answer: A
Why: Without an operational definition, different people produce different numbers for the same process.

### M01 | Measure
A Gage R&R study gives 25% of study variation and ndc = 6. The measurement system is:
- A) Acceptable
- B) Conditionally acceptable
- C) Unacceptable
- D) Impossible to judge
Answer: B
Why: Under 10% is acceptable, 10-30% conditionally acceptable depending on the application, over 30% unacceptable; ndc >= 5 is met.

### M02 | Measure
The minimum recommended number of distinct categories (ndc) for a gauge used for process control is:
- A) 2
- B) 3
- C) 5
- D) 10
Answer: C
Why: AIAG recommends ndc of 5 or more.

### M03 | Measure
USL = 10.6, LSL = 9.4 and sigma = 0.1. What is Cp?
- A) 1.00
- B) 1.33
- C) 2.00
- D) 4.00
Answer: C
Why: Cp = (USL - LSL) / 6 sigma = 1.2 / 0.6 = 2.0.

### M04 | Measure
Same process: USL 10.6, LSL 9.4, sigma 0.1, mean 10.2. What is Cpk?
- A) 1.33
- B) 2.00
- C) 2.67
- D) 0.67
Answer: A
Why: Cpk = min((10.6 - 10.2) / 0.3, (10.2 - 9.4) / 0.3) = min(1.33, 2.67) = 1.33.

### M05 | Measure
"Number of scratches per panel" is what type of data?
- A) Continuous
- B) Count (discrete)
- C) Ordinal
- D) Nominal
Answer: B
Why: Counts of defects per unit are discrete; they are charted with c or u charts.

### M06 | Measure
Subgroups of 5 give R-bar = 0.4652 (d2 = 2.326). What is the within-subgroup sigma estimate?
- A) 0.093
- B) 0.200
- C) 0.465
- D) 1.082
Answer: B
Why: sigma = R-bar / d2 = 0.4652 / 2.326 = 0.200.

### A01 | Analyze
To compare mean tensile strength from three suppliers (normal data), use:
- A) Chi-square test
- B) One-way ANOVA
- C) Paired t-test
- D) 2-proportion test
Answer: B
Why: A continuous Y across three or more groups is compared with one-way ANOVA.

### A02 | Analyze
A test gives p = 0.03 with alpha = 0.05. The correct conclusion is:
- A) Fail to reject H0
- B) Reject H0
- C) Accept H0
- D) H1 is proven false
Answer: B
Why: p < alpha, so reject the null hypothesis; we never "accept" H0.

### A03 | Analyze
A type II error is:
- A) Rejecting a true null hypothesis
- B) Failing to reject a false null hypothesis
- C) The same as alpha
- D) Using the wrong test
Answer: B
Why: Beta (type II) is missing a real difference; alpha (type I) is a false alarm.

### A04 | Analyze
A correlation coefficient r = -0.9 means:
- A) A weak negative relationship
- B) A strong negative linear relationship
- C) X causes Y to fall
- D) No relationship
Answer: B
Why: |r| close to 1 is a strong linear relationship; correlation does not prove causation.

### A05 | Analyze
A simple regression has R-sq = 0.64 and a positive slope. What is r?
- A) 0.41
- B) 0.64
- C) 0.80
- D) 0.32
Answer: C
Why: For simple linear regression r = sqrt(R-sq) = 0.8, with the sign of the slope.

### A06 | Analyze
To compare the defective rates (pass/fail) of two shifts, use:
- A) 2-sample t-test
- B) 2-proportion test
- C) One-way ANOVA
- D) F-test
Answer: B
Why: The output is attribute (proportion defective) and there are two groups.

### I01 | Improve
How many runs does a 2^(5-1) fractional factorial design have (no replicates, no centre points)?
- A) 8
- B) 16
- C) 32
- D) 10
Answer: B
Why: 2^(5-1) = 2^4 = 16 runs.

### I02 | Improve
In a resolution IV design:
- A) Main effects are aliased with two-factor interactions
- B) Main effects are clear of two-factor interactions, which are aliased with each other
- C) All main effects and two-factor interactions are clear
- D) There is no aliasing
Answer: B
Why: Resolution IV: shortest word in the defining relation has 4 letters.

### I03 | Improve
The response averages 52 at the high level of factor A and 46 at the low level. The effect of A is:
- A) 3
- B) 6
- C) 49
- D) 98
Answer: B
Why: Effect = mean(high) - mean(low) = 6; the coded regression coefficient is half of it (3).

### I04 | Improve
Poka-yoke means:
- A) Mistake-proofing
- B) 5S
- C) Visual management
- D) Kanban
Answer: A
Why: Poka-yoke devices prevent or immediately detect errors.

### I05 | Improve
Why is the run order of an experiment randomised?
- A) To reduce the number of runs
- B) To protect against lurking variables and time trends
- C) To increase the resolution
- D) To remove interactions
Answer: B
Why: Randomisation spreads unknown time-related effects across all factor settings.

### I06 | Improve
Centre points added to a two-level factorial allow you to detect:
- A) Interactions
- B) Curvature
- C) Aliasing
- D) Blocks
Answer: B
Why: Comparing the centre mean with the factorial mean tests for curvature (and gives pure error).

### C01 | Control
X-double-bar = 50, R-bar = 4, n = 5 (A2 = 0.577). What is the UCL of the X-bar chart?
- A) 52.31
- B) 54.00
- C) 51.15
- D) 56.92
Answer: A
Why: UCL = 50 + 0.577 x 4 = 52.31.

### C02 | Control
Which chart is used for fraction defective with a varying sample size?
- A) np chart
- B) p chart
- C) c chart
- D) u chart
Answer: B
Why: p charts plot the fraction defective and allow limits to vary with n.

### C03 | Control
Eight consecutive points on one side of the centre line most likely indicate:
- A) Normal variation
- B) A shift in the process mean
- C) Increased variation only
- D) Over-control
Answer: B
Why: A run of 8 (Western Electric rule 4) signals a sustained shift.

### C04 | Control
When an out-of-specification part is found, the reaction plan should first:
- A) Adjust the machine and continue
- B) Stop, contain suspect product since the last good check, then correct
- C) Recalculate the control limits
- D) Increase the sample size next week
Answer: B
Why: Containment protects the customer; correction follows.

### C05 | Control
Control limits are calculated from:
- A) The specification limits
- B) Process data
- C) The customer's requirements
- D) The engineering drawing
Answer: B
Why: Control limits describe the voice of the process; specifications are the voice of the customer.

### C06 | Control
At the end of the Control phase, ownership of the improved process is handed to the:
- A) Champion
- B) Process owner
- C) Master black belt
- D) Finance team
Answer: B
Why: The process owner keeps the control plan alive; finance only validates savings.
