from . import adzuna, amazon, ashby, greenhouse, jibe, lever, readme_table, simplify, smartrecruiters, themuse, usajobs, workday

COLLECTORS = {
    "workday": workday.collect,
    "greenhouse": greenhouse.collect,
    "lever": lever.collect,
    "ashby": ashby.collect,
    "smartrecruiters": smartrecruiters.collect,
    "amazon": amazon.collect,
    "jibe": jibe.collect,
    "themuse": themuse.collect,
    "simplify": simplify.collect,
    "readme_table": readme_table.collect,
    "adzuna": adzuna.collect,
    "usajobs": usajobs.collect,
}
