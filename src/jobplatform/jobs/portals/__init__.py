from jobplatform.jobs.portals.registry import portal_registry
from jobplatform.jobs.portals.naukri import NaukriAdapter
from jobplatform.jobs.portals.linkedin import LinkedInAdapter
from jobplatform.jobs.portals.indeed import IndeedAdapter
from jobplatform.jobs.portals.wellfound import WellFoundAdapter

portal_registry.register(NaukriAdapter())
portal_registry.register(LinkedInAdapter())
portal_registry.register(IndeedAdapter())
portal_registry.register(WellFoundAdapter())

__all__ = ["portal_registry"]
