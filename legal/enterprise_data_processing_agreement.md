# Enterprise Data Processing Agreement

**PARWA AI Customer Support Platform**

**Version:** 2.0  
**Effective Date:** [Date]  
**Last Updated:** March 2026

---

## 1. PARTIES

This Data Processing Agreement ("DPA") is entered into between:

**Data Processor:** PARWA Technologies Inc. ("PARWA", "we", "us", "our")  
Address: [Company Address]  
Contact: privacy@parwa.ai

**Data Controller:** [Enterprise Client Name] ("Client", "you", "your")

Collectively referred to as the "Parties."

---

## 2. DEFINITIONS

### 2.1 Key Terms

- **"Personal Data"** means any information relating to an identified or identifiable natural person.
- **"Data Subject"** means an individual whose Personal Data is processed.
- **"Processing"** means any operation performed on Personal Data, whether automated or manual.
- **"Data Controller"** means the entity determining purposes and means of Processing.
- **"Data Processor"** means the entity Processing Personal Data on behalf of the Data Controller.
- **"Sub-processor"** means a third party engaged by PARWA to Process Personal Data.
- **"Services"** means the PARWA AI customer support platform services.
- **"Security Incident"** means any unauthorized access, disclosure, or breach of Personal Data.

### 2.2 Regulatory References

- **"GDPR"** means the General Data Protection Regulation (EU) 2016/679.
- **"CCPA"** means the California Consumer Privacy Act.
- **"Applicable Data Protection Laws"** means all applicable privacy and data protection laws.

---

## 3. SCOPE AND PURPOSE

### 3.1 Scope

This DPA applies to the Processing of Personal Data by PARWA on behalf of the Client in connection with the Services.

### 3.2 Purpose

The purpose of this DPA is to:

1. Define the obligations of each Party regarding Personal Data Processing
2. Ensure compliance with Applicable Data Protection Laws
3. Protect the rights and freedoms of Data Subjects
4. Establish security standards and breach notification procedures

---

## 4. DETAILS OF PROCESSING

### 4.1 Categories of Data Subjects

PARWA Processes Personal Data relating to the following categories of Data Subjects:

- Client's customers and end users
- Client's employees and authorized users
- Support ticket submitters
- Website visitors (when applicable)

### 4.2 Categories of Personal Data

| Category | Examples | Retention Period |
|----------|----------|------------------|
| Contact Information | Name, email, phone, address | Duration of service + 30 days |
| Account Information | Username, password (hashed), preferences | Duration of service + 30 days |
| Support Interaction Data | Tickets, chat logs, email correspondence | Duration of service + 90 days |
| Technical Data | IP address, device information, browser type | 90 days |
| Payment Information | Billing address, payment method (tokenized) | As required by law |

### 4.3 Processing Activities

| Activity | Purpose | Legal Basis |
|----------|---------|-------------|
| Customer support ticket handling | Provide support services | Contract performance |
| AI-powered response generation | Improve support efficiency | Legitimate interest |
| Analytics and reporting | Service improvement | Legitimate interest |
| Data storage | Service delivery | Contract performance |
| Data backup | Business continuity | Legitimate interest |

### 4.4 Processing Location

Personal Data is processed in the following locations:

- **Primary:** United States (us-east-1)
- **EU Region:** Ireland (eu-west-1) - for EU clients
- **APAC Region:** Singapore (ap-southeast-1) - for APAC clients

---

## 5. OBLIGATIONS OF THE PARTIES

### 5.1 Client Obligations

The Client agrees to:

1. Comply with Applicable Data Protection Laws as Data Controller
2. Provide lawful instructions to PARWA for Processing
3. Ensure appropriate legal bases for Processing
4. Implement appropriate technical and organizational measures
5. Conduct data protection impact assessments where required
6. Maintain records of Processing activities
7. Notify PARWA of any changes to Processing requirements

### 5.2 PARWA Obligations

PARWA agrees to:

1. Process Personal Data only on documented instructions from the Client
2. Ensure personnel authorized to Process Personal Data are bound by confidentiality
3. Implement and maintain appropriate security measures
4. Engage Sub-processors only with prior written authorization
5. Assist the Client in responding to Data Subject requests
6. Assist the Client in ensuring compliance with security obligations
7. Delete or return Personal Data upon termination
8. Submit to audits and inspections
9. Notify the Client of any Security Incident without undue delay

---

## 6. SECURITY MEASURES

### 6.1 Technical Security Measures

PARWA implements the following technical security measures:

#### 6.1.1 Access Controls

- Role-based access control (RBAC)
- Multi-factor authentication (MFA) for all administrative access
- IP allowlisting for enterprise clients
- Session management with automatic timeout
- Regular access reviews

#### 6.1.2 Encryption

- TLS 1.3 for data in transit
- AES-256 encryption for data at rest
- Encryption key management via AWS KMS
- Separate encryption keys per tenant

#### 6.1.3 Infrastructure Security

- Kubernetes-based container orchestration
- Network segmentation with VPCs
- Web Application Firewall (WAF)
- DDoS protection
- Regular penetration testing

#### 6.1.4 Monitoring and Logging

- 24/7 security monitoring
- SIEM integration
- Audit logging of all access
- Anomaly detection

### 6.2 Organizational Security Measures

- Security awareness training for all personnel
- Background checks for employees with data access
- Information security policies
- Incident response procedures
- Business continuity and disaster recovery plans

---

## 7. SUB-PROCESSORS

### 7.1 Current Sub-processors

The Client authorizes PARWA to use the following Sub-processors:

| Sub-processor | Purpose | Location | DPA Available |
|---------------|---------|----------|---------------|
| Amazon Web Services | Cloud infrastructure | US, EU, APAC | Yes |
| Supabase | Database hosting | US, EU | Yes |
| OpenRouter | AI model access | US | Yes |
| Twilio | SMS and Voice services | US | Yes |
| Brevo | Email delivery | EU | Yes |

### 7.2 Sub-processor Changes

PARWA will:

1. Provide at least 30 days' notice before adding or replacing Sub-processors
2. Provide information about the Sub-processor's Processing activities
3. Allow the Client to object to new Sub-processors
4. Ensure Sub-processors are bound by equivalent data protection obligations

---

## 8. DATA SUBJECT RIGHTS

### 8.1 Supported Rights

PARWA supports the following Data Subject rights under GDPR:

- Right of access (Article 15)
- Right to rectification (Article 16)
- Right to erasure (Article 17)
- Right to restriction (Article 18)
- Right to data portability (Article 20)
- Right to object (Article 21)
- Rights related to automated decision-making (Article 22)

### 8.2 Request Handling Process

1. Client receives request from Data Subject
2. Client verifies identity of Data Subject
3. Client submits verified request to PARWA
4. PARWA processes request within 30 days
5. PARWA provides response to Client
6. Client communicates response to Data Subject

---

## 9. SECURITY INCIDENT NOTIFICATION

### 9.1 Notification Procedure

In the event of a Security Incident, PARWA will:

1. Notify the Client within 72 hours of becoming aware
2. Provide initial details including:
   - Nature of the incident
   - Categories and approximate number of Data Subjects affected
   - Likely consequences
   - Measures taken to address the incident
3. Provide updates as new information becomes available
4. Assist the Client in meeting breach notification obligations

### 9.2 Incident Response

PARWA maintains an incident response plan that includes:

- Incident identification and classification
- Containment procedures
- Eradication and recovery
- Post-incident review
- Documentation and reporting

---

## 10. DATA RETENTION AND DELETION

### 10.1 Retention Periods

Personal Data is retained for:

- Active service duration: As long as the Services are active
- Post-termination: Maximum 90 days (for data export)
- Legal hold: As required by applicable law

### 10.2 Deletion Procedures

Upon termination of the Services:

1. Client may request data export within 30 days
2. PARWA will delete all Personal Data within 90 days
3. Deletion will be verified and documented
4. Deletion certificates will be provided upon request

---

## 11. AUDIT RIGHTS

The Client has the right to:

1. Request information about PARWA's Processing activities
2. Request evidence of PARWA's compliance with this DPA
3. Conduct audits or inspections with reasonable notice
4. Receive copies of audit reports from PARWA's certifying bodies

---

## 12. LIABILITY AND INDEMNIFICATION

### 12.1 Liability

Each Party's liability shall be limited as set forth in the Master Services Agreement.

### 12.2 Indemnification

PARWA will indemnify the Client against claims arising from PARWA's violation of Applicable Data Protection Laws.

---

## 13. TERM AND TERMINATION

This DPA remains in effect for the duration of the Services. Upon termination:

1. All Personal Data will be returned or deleted
2. Ongoing confidentiality obligations survive
3. Audit rights continue for 12 months

---

## 14. GOVERNING LAW

This DPA is governed by the laws of [Jurisdiction] and any disputes shall be resolved in [Courts].

---

## 15. CONTACT INFORMATION

**Data Protection Officer:**  
Email: dpo@parwa.ai  
Address: [Address]

**Security Team:**  
Email: security@parwa.ai

---

**Signatures**

________________________  
PARWA Technologies Inc.  
Date: ________________

________________________  
[Enterprise Client Name]  
Date: ________________
