# Domain Feature Playbooks

Starting lists that repeatedly carry signal. Every feature is computed as of the prediction time.

## Subscription churn
- Tenure (days), plan, price paid vs list price, recent price change, contract type, days to renewal.
- Usage: sessions/logins in 7/30/90 d, trend (7 d vs previous 30 d average), days since last use, core-feature
  usage, breadth of features used.
- Support: tickets in 90 d, unresolved tickets, sentiment of last ticket, time to resolution.
- Billing: failed payments in 90 d, payment method, card expiry within 30 d, discounts ending.
- Social/network: seats used / seats bought, team members leaving.
- Leaks to avoid: cancellation reason, retention offer accepted, account status read today.

## Card / payment fraud
- Velocity per card, device, IP, email, merchant: counts and sums in 10 min / 1 h / 24 h / 7 d.
- Amount vs card's own history (ratio, z-score), round amounts, small "test" transactions before a large one.
- Novelty: first time this merchant / country / device / shipping address for the card.
- Geography: distance from home, impossible travel, billing vs shipping mismatch, IP country vs card country.
- Merchant risk: historical fraud rate of the merchant (out-of-fold), merchant category.
- Time: hour in local time, night-time flag.
- Leaks: chargeback flag, analyst decision, case status.

## Credit risk
- Bureau data: utilisation (balance / limit), delinquencies in 12/24 months, inquiries in 6 months, age of
  oldest account, number of open accounts.
- Affordability: debt-to-income, payment-to-income, income stability.
- Behaviour (existing customers): days past due history, payment ratio, cash advances, limit increases.
- Application: loan amount / income, term, purpose.
- Regulated: avoid protected attributes and close proxies; monotone constraints for explainability.

## Retail demand forecasting
- Lags: sales at t−7, t−14, t−28, t−364 (horizon-aware: lags must be >= horizon for direct models).
- Rolling means/medians/std over 7/28/91 days, shifted by the horizon.
- Calendar: day of week, week of year, month, holidays, paydays, school holidays, events.
- Price: price, discount depth, price vs 28-day average, promotion flags (planned only).
- Product/store: category, store size, store-level trends, product age.
- Stock-outs: flag censored days; do not train on them as zero demand.

## Marketing response / conversion
- Recency of last purchase/visit, frequency, monetary value.
- Engagement with past campaigns: opens, clicks, conversions per channel.
- Channel preference, device, time since last contact (fatigue).
- Product affinity: categories bought, browsing in the last 7 days.
- For uplift: same features; the treatment must be randomised.

## Real estate pricing
- Size (log sqft), rooms, bathrooms, lot size, age, renovation recency.
- Location: neighbourhood, distance to centre/transit/schools, local median price per sqft (out-of-fold).
- Quality/condition grades, amenities (pool, garage), floor level, view.
- Market timing: month of sale, local price index at sale date.
- Leaks: final sale price-derived fields, assessed value updated after sale.

## IoT / predictive maintenance
- Sensor statistics over windows: mean, std, min, max, slope, range, skew over 1 h / 24 h / 7 d.
- Deviations from the machine's own baseline (z-score vs its last 30 days).
- Frequency-domain features (FFT band energy) for vibration.
- Operating context: load, temperature, duty cycle, hours since last maintenance, maintenance count.
- Cross-sensor ratios (temperature per unit load).
- Leaks: maintenance work orders created after the failure, failure codes.

## Healthcare (readmission, risk)
- Prior utilisation: admissions/ED visits in 6/12 months, length of stay.
- Diagnoses grouped into chapters or comorbidity indices (Charlson, Elixhauser).
- Medications count, high-risk medications, lab trends (last value, slope, abnormal flags).
- Social determinants where allowed.
- Leaks: discharge disposition coded after the outcome, billing codes finalised later.

## B2B lead scoring
- Firmographics: industry, employee count band, revenue band, region.
- Engagement: website visits in 7/30 d, pricing-page views, content downloads, email replies.
- Fit: match to ideal customer profile, technology stack signals.
- Timing: days since first touch, days since last activity, recent funding or hiring.
- Leaks: opportunity stage, "sales accepted" flags set after qualification.
