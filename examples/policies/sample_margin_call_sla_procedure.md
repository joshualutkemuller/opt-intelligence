# Margin Call SLA Procedure

Portfolio PORT_MARGIN_OPS_550 uses the margin call workflow for same-day queue
triage during market stress.

Operations capacity for the current review window is 165 minutes. Margin calls
of $25 million or more meet the materiality threshold and require supervisor
review. Calls due within 2 hours require SLA escalation. Dispute probability
stress should be set to 125% for the stress queue review.

This procedure is a production constraint change for demonstration purposes.
