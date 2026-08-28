{
    "name": "Job Hunter Management",
    "summary": "Track job opportunities and applications",
    "version": "16.0.3.0.0",
    "category": "Human Resources",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/job_hunter_sources.xml",
        "views/job_application_views.xml",
        "views/job_hunter_search_views.xml",
    ],
    "application": True,
    "installable": True,
}
