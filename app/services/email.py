from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from flask import current_app
import os

class EmailService:
    """Service for handling email notifications using SendGrid"""
    
    @staticmethod
    def send_lead_notification(company_data, partner_data=None):
        """Send notification when a new lead submits the form"""
        try:
            # Log the attempt to send email
            current_app.logger.info(f"Attempting to send lead notification email for company: {company_data.get('name')}")
            
            # Get recipients
            recipients = [
                os.environ.get('SALES_TEAM_EMAIL'),
                'nicolas.mopi94@gmail.com'
            ]
            recipients = [email for email in recipients if email]  # Filter out None values
            
            # Log SendGrid configuration
            current_app.logger.info(f"Using SendGrid configuration: FROM_EMAIL={os.environ.get('SENDGRID_FROM_EMAIL')}, TO_EMAILS={recipients}")
            
            # Verify API key exists
            api_key = os.environ.get('SENDGRID_API_KEY')
            if not api_key:
                current_app.logger.error("SendGrid API key is missing!")
                return False
                
            sg = SendGridAPIClient(api_key)
            
            # Format the message
            subject = f"New Lead: {company_data.get('name', 'Unknown Company')}"
            
            # Build the email content
            content = f"""
            New lead form submission:
            
            Company Details:
            - Company Name: {company_data.get('name', 'N/A')}
            - Contact Name: {company_data.get('contact_name', 'N/A')}
            - Email: {company_data.get('email', 'N/A')}
            - Phone: {company_data.get('phone', 'N/A')}
            - Service Interest: {company_data.get('service_type', 'N/A')}
            - Preferred Contact Time: {company_data.get('preferred_contact_time', 'N/A')}
            
            Additional Information:
            {company_data.get('additional_info', 'No additional information provided.')}
            """
            
            if partner_data:
                content += f"""
                
                Referred by:
                - Partner Name: {partner_data.get('name', 'N/A')}
                - Partner Email: {partner_data.get('email', 'N/A')}
                """
            
            # Log email content
            current_app.logger.info(f"Preparing email with subject: {subject}")
            
            # Create the email message with multiple recipients
            message = Mail(
                from_email=Email(os.environ.get('SENDGRID_FROM_EMAIL')),
                to_emails=[To(email) for email in recipients],
                subject=subject,
                plain_text_content=Content("text/plain", content.strip())
            )
            
            # Add custom headers to improve deliverability
            message.header_operations = {
                "X-Priority": "1",
                "X-MSMail-Priority": "High",
                "Importance": "High",
                "X-Entity-Ref-ID": company_data.get('name', '')
            }
            
            # Send the email
            current_app.logger.info(f"Sending email via SendGrid to {len(recipients)} recipients...")
            response = sg.send(message)
            
            # Log the response
            current_app.logger.info(f"SendGrid Response - Status Code: {response.status_code}")
            if response.status_code == 202:
                current_app.logger.info("Email sent successfully!")
                return True
            else:
                current_app.logger.error(f"Failed to send email. Status code: {response.status_code}")
                return False
            
        except Exception as e:
            current_app.logger.error(f"Failed to send lead notification email: {str(e)}")
            return False 