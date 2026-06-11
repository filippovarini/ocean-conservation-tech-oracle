"""Controlled vocabulary for the ocean-tech catalog.

These are the facets the extractor maps source text onto. To grow the
taxonomy, add a key here — the LLM prompt is built from these lists, so a
new key starts being used on the next run. Anything the model invents that
is NOT in these lists gets demoted to `free_tags` (and is a signal that a
term might be worth promoting into the vocab).
"""

# Multi-valued descriptive facets ------------------------------------------

MODALITIES = [
    "optical_imagery",          # photos, BRUVS stills, camera traps
    "video",                    # ROV/AUV/BRUVS video
    "bioacoustics_pam",         # passive acoustic monitoring, hydrophones
    "active_acoustics",         # echosounder, multibeam, sonar
    "edna_genomic",             # eDNA, metabarcoding, genomics
    "satellite_remote_sensing",
    "aerial_drone",
    "telemetry_tracking",       # tags, acoustic/satellite telemetry
    "environmental_sensors",    # temp, pH, oxygen, etc.
    "diver_survey",
]

FUNCTIONS = [
    "species_detection_id",
    "abundance_density",
    "biodiversity_assessment",
    "individual_id_reid",
    "habitat_mapping",
    "behaviour_analysis",
    "mpa_surveillance_enforcement",
    "environmental_monitoring",
    "data_platform",            # annotation, storage, pipelines
    "analytics_modelling",
]

HABITATS = [
    "coral_reef",
    "rocky_reef",
    "seagrass_macroalgae",
    "mangrove_estuary",
    "open_ocean_pelagic",
    "deep_sea_benthic",
    "polar",
    "coastal_intertidal",
]

TAXA = [
    "fish",
    "elasmobranchs",
    "marine_mammals",
    "sea_turtles",
    "seabirds",
    "benthic_invertebrates",
    "plankton",
    "all_biodiversity",
    "habitat_only",
]

# Single-valued ordinal / categorical facets --------------------------------

MATURITY = [
    "concept_research",
    "prototype",
    "field_tested",
    "commercial_product",
    "widely_adopted",
]

OPENNESS = [
    "open_source",
    "open_core_freemium",
    "commercial_proprietary",
    "academic_internal",
    "unknown",
]

# Helpers -------------------------------------------------------------------

MULTI_FACETS = {
    "modalities": MODALITIES,
    "functions": FUNCTIONS,
    "habitats": HABITATS,
    "taxa": TAXA,
}
SINGLE_FACETS = {
    "maturity": MATURITY,
    "openness": OPENNESS,
}


def vocab_prompt_block() -> str:
    """Render the vocabulary as a block to inject into the extraction prompt."""
    lines = []
    for name, values in MULTI_FACETS.items():
        lines.append(f"{name} (choose any that apply): {', '.join(values)}")
    for name, values in SINGLE_FACETS.items():
        lines.append(f"{name} (choose exactly one): {', '.join(values)}")
    return "\n".join(lines)
