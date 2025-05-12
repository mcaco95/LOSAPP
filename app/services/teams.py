import requests
import os
from flask import current_app
from datetime import datetime

class TeamsService:
    """Service for handling Microsoft Teams notifications"""
    
    @staticmethod
    def send_lead_notification(company_data, partner_data=None):
        """Send notification to Teams when a new lead submits the form"""
        try:
            webhook_url = os.environ.get('TEAMS_WEBHOOK_URL')
            if not webhook_url:
                current_app.logger.error("Teams webhook URL is missing!")
                return False

            # Create Teams message card
            card = {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": {
                            "type": "AdaptiveCard",
                            "version": "1.0",
                            "body": [
                                {
                                    "type": "TextBlock",
                                    "size": "Large",
                                    "weight": "Bolder",
                                    "color": "Accent",
                                    "text": f"🎯 New Lead: {company_data.get('name', 'Unknown Company')}"
                                },
                                {
                                    "type": "FactSet",
                                    "facts": [
                                        {
                                            "title": "Contact Name",
                                            "value": company_data.get('contact_name', 'N/A')
                                        },
                                        {
                                            "title": "Email",
                                            "value": company_data.get('email', 'N/A')
                                        },
                                        {
                                            "title": "Phone",
                                            "value": company_data.get('phone', 'N/A')
                                        },
                                        {
                                            "title": "Service Interest",
                                            "value": company_data.get('service_type', 'N/A')
                                        },
                                        {
                                            "title": "Preferred Time",
                                            "value": company_data.get('preferred_contact_time', 'N/A')
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ]
            }

            # Add partner information if available
            if partner_data:
                card["attachments"][0]["content"]["body"].append({
                    "type": "TextBlock",
                    "text": f"👤 Referred by: {partner_data.get('name', 'N/A')} ({partner_data.get('email', 'N/A')})",
                    "wrap": True,
                    "color": "Good"
                })

            # Add additional information if available
            if company_data.get('additional_info'):
                card["attachments"][0]["content"]["body"].append({
                    "type": "TextBlock",
                    "text": "📝 Additional Information:",
                    "weight": "Bolder",
                    "wrap": True
                })
                card["attachments"][0]["content"]["body"].append({
                    "type": "TextBlock",
                    "text": company_data.get('additional_info'),
                    "wrap": True,
                    "isSubtle": True
                })

            # Add timestamp
            card["attachments"][0]["content"]["body"].append({
                "type": "TextBlock",
                "text": f"⏰ Submitted: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
                "wrap": True,
                "isSubtle": True,
                "size": "Small"
            })

            # Send the notification
            current_app.logger.info("Sending Teams notification...")
            response = requests.post(
                webhook_url,
                json=card
            )

            if response.status_code == 200:
                current_app.logger.info("Teams notification sent successfully!")
                return True
            else:
                current_app.logger.error(f"Failed to send Teams notification. Status code: {response.status_code}")
                return False

        except Exception as e:
            current_app.logger.error(f"Failed to send Teams notification: {str(e)}")
            return False 