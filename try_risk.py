import json

import risk_tools

scam = """Urgent hiring! Work from home, no experience required. Earn $300 per day guaranteed.
Pay a refundable registration fee of $50 to secure your laptop. Interviews are on Telegram.
Send a copy of your passport and bank details to hr.globaltech@gmail.com"""

print("=== SCAM-STYLE POSTING ===")
print(json.dumps(risk_tools.check("GlobalTech Solutions", "http://bit.ly/apply-now", scam, "",
                                  "Data Entry Clerk", verify_board=False), indent=2))

print("=== REAL ROLE ON A REAL BOARD ===")
print(json.dumps(risk_tools.check("Stripe", "https://stripe.com/jobs/search?gh_jid=8144196", "", "",
                                  "AI Engineer", verify_board=True), indent=2))

print("=== LOOKALIKE DOMAIN CLAIMING TO BE STRIPE ===")
print(json.dumps(risk_tools.check("Stripe", "https://stripe-careers-apply.com/data-entry",
                                  "Apply now.", "recruiter@stripe-hiring.net",
                                  "Remote Data Entry Specialist", verify_board=True), indent=2))