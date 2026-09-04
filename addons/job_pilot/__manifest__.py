{
    "name": "Job Pilot",
    "summary": "Manage personal career profiles and import data from uploaded CVs",
    "description": """
Job Pilot - Career Profile
===========================

Lets each internal user maintain a structured career profile (personal
information, professional title/summary/attributes, skills, work
experience with projects, education, certifications, languages,
leadership/volunteering, references and additional information) and
upload a CV (PDF/DOCX) to extract candidate data through an
extract -> parse -> review -> import workflow, without ever overwriting
existing profile data without explicit confirmation.
""",
    "version": "16.0.1.0.0",
    "category": "Human Resources/Recruitment",
    "license": "LGPL-3",
    "author": "Job Pilot",
    "depends": ["base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/job_pilot_data.xml",
        "views/job_pilot_profile_views.xml",
        "views/job_pilot_skill_views.xml",
        "views/job_pilot_cv_upload_views.xml",
        "views/res_config_settings_views.xml",
        "views/job_pilot_menus.xml",
    ],
    "application": True,
    "installable": True,
}
