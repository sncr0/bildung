"""One-shot enrichment seed: streams, significance, collections, and work expansion.

Run with:
    uv run python -m bildung.ingestion.seed_enrichments
"""
from __future__ import annotations

import asyncio

from bildung.config import settings
from bildung.db.neo4j import build_driver
from bildung.ids import author_id as _author_id
from bildung.ids import collection_id as _coll_id
from bildung.ids import stream_id as _stream_id
from bildung.ids import work_id as _work_id


# ---------------------------------------------------------------------------
# Significance (kept for display / backward compat)
# ---------------------------------------------------------------------------

SIGNIFICANCE: list[tuple[str, str, str]] = [
    ("Crime and Punishment",       "Dostoyevsky", "major"),
    ("The Idiot",                  "Dostoyevsky", "major"),
    ("The Brothers Karamazov",     "Dostoyevsky", "major"),
    ("Notes from the Underground", "Dostoyevsky", "major"),
    ("Demons",                     "Dostoyevsky", "major"),
    ("Adolescent",                 "Dostoyevsky", "major"),
    ("Bobok",                      "Dostoyevsky", "minor"),
    ("White Nights",               "Dostoyevsky", "minor"),
    ("Short Stories",              "Dostoevsky",  "minor"),
    ("Poor Folk",                  "Dostoyevsky", "minor"),
    ("Gambler",                    "Dostoyevsky", "minor"),
    ("Spring Snow",                "Mishima",     "major"),
    ("Runaway Horses",             "Mishima",     "major"),
    ("Temple of Dawn",             "Mishima",     "major"),
    ("Decay of the Angel",         "Mishima",     "major"),
    ("Confessions of a Mask",      "Mishima",     "major"),
    ("Sailor who Fell",            "Mishima",     "major"),
    ("Temple of the Golden",       "Mishima",     "major"),
    ("Symposium",                  "Plato",       "major"),
    ("Phaedrus",                   "Plato",       "major"),
    ("Apologia",                   "Plato",       "major"),
    ("Republic",                   "Plato",       "major"),
    ("Phaedo",                     "Plato",       "major"),
    ("Crito",                      "Plato",       "minor"),
    ("Meno",                       "Plato",       "minor"),
    ("Anna Karenina",              "Tolstoy",     "major"),
    ("War and Peace",              "Tolstoy",     "major"),
    ("Death of Ivan Ilyich",       "Tolstoy",     "major"),
    ("Kreutzer Sonata",            "Tolstoy",     "minor"),
    ("Twilight of the Idols",      "Nietzsche",   "major"),
    ("Beyond Good and Evil",       "Nietzsche",   "major"),
    ("Thus Spoke Zarathustra",     "Nietzsche",   "major"),
    ("Gay Science",                "Nietzsche",   "major"),
    ("The Stranger",               "Camus",       "major"),
    ("The Plague",                 "Camus",       "major"),
    ("The Fall",                   "Camus",       "major"),
    ("Myth of Sisyphus",           "Camus",       "major"),
    ("Dead Souls",                 "Gogol",       "major"),
    ("Short Stories",              "Gogol",       "minor"),
    ("Macbeth",                    "Shakespeare", "major"),
    ("Hamlet",                     "Shakespeare", "major"),
    ("King Lear",                  "Shakespeare", "major"),
    ("Othello",                    "Shakespeare", "major"),
    ("Midsummer Night's Dream",    "Shakespeare", "major"),
    ("Steppenwolf",                "Hesse",       "major"),
    ("Siddhartha",                 "Hesse",       "major"),
    ("Glass Bead Game",            "Hesse",       "major"),
    ("Narcissus and Goldmund",     "Hesse",       "major"),
    ("Demian",                     "Hesse",       "major"),
    ("Ondraaglijke Lichtheid",     "Kundera",     "major"),
    ("The Farewell Party",         "Kundera",     "minor"),
    ("Het Gezin Van Paemel",       "Buysse",      "major"),
    ("Recht van de Sterkste",      "Buysse",      "major"),
    ("De Biezenstekker",           "Buysse",      "minor"),
    ("Broeder en Zuster",          "Buysse",      "minor"),
    ("Lente",                      "Buysse",      "minor"),
    ("De Vlaschaard",              "Streuvels",   "major"),
    ("leven en dood",              "Streuvels",   "major"),
    ("Le Rouge et le Noir",        "Stendhal",    "major"),
    ("Vanina Vanini",              "Stendhal",    "minor"),
    ("Abbesse de Castro",          "Stendhal",    "minor"),
    ("De Toverberg",               "Mann",        "major"),
    ("Doctor Zhivago",             "Pasternak",   "major"),
    ("Heart of Darkness",          "Conrad",      "major"),
    ("Lolita",                     "Nabokov",     "major"),
    ("Picture of Dorian Gray",     "Wilde",       "major"),
    ("Le Père Goriot",             "Balzac",      "major"),
    ("American Psycho",            "Ellis",       "major"),
    ("Meditations on First",       "Descartes",   "major"),
    ("The Prince",                 "Machiavelli", "major"),
    ("An Enquiry",                 "Hume",        "major"),
    ("Discourse on Metaphysics",   "Leibniz",     "major"),
    ("The Trial",                  "Kafka",       "major"),
    ("The Castle",                 "Kafka",       "major"),
    ("The Metamorphosis",          "Kafka",       "major"),
    ("Swann's Way",                "Proust",      "major"),
    ("Madame Bovary",              "Flaubert",    "major"),
    ("Sentimental Education",      "Flaubert",    "major"),
    ("Three Sisters",              "Chekhov",     "major"),
    ("Cherry Orchard",             "Chekhov",     "major"),
    ("Uncle Vanya",                "Chekhov",     "major"),
]

# ---------------------------------------------------------------------------
# New authors to create (with metadata)
# ---------------------------------------------------------------------------

NEW_AUTHORS: list[dict] = [
    {"name": "Marcel Proust",    "birth_year": 1871, "death_year": 1922, "nationality": "French",  "primary_language": "FR"},
    {"name": "Franz Kafka",      "birth_year": 1883, "death_year": 1924, "nationality": "Czech",   "primary_language": "DE"},
    {"name": "Anton Chekhov",    "birth_year": 1860, "death_year": 1904, "nationality": "Russian", "primary_language": "RU"},
    {"name": "Gustave Flaubert", "birth_year": 1821, "death_year": 1880, "nationality": "French",  "primary_language": "FR"},
]

# (title, author_name, language, source_type)
NEW_WORKS: list[tuple[str, str, str, str]] = [
    # Dostoyevsky expansion
    ("The Demons",                              "Fyodor Dostoyevsky", "EN", "fiction"),
    ("The Adolescent",                          "Fyodor Dostoyevsky", "EN", "fiction"),
    ("Poor Folk",                               "Fyodor Dostoyevsky", "EN", "fiction"),
    ("The Gambler",                             "Fyodor Dostoyevsky", "EN", "fiction"),
    # Tolstoy expansion
    ("War and Peace",                           "Leo Tolstoy",        "EN", "fiction"),
    ("The Kreutzer Sonata",                     "Leo Tolstoy",        "EN", "fiction"),
    # Mishima expansion
    ("The Decay of the Angel",                  "Yukio Mishima",      "EN", "fiction"),
    ("The Temple of the Golden Pavilion",       "Yukio Mishima",      "EN", "fiction"),
    # Plato expansion
    ("The Republic",                            "Plato",              "EN", "primary"),
    ("Phaedo",                                  "Plato",              "EN", "primary"),
    ("Meno",                                    "Plato",              "EN", "primary"),
    # Camus expansion
    ("The Plague",                              "Albert Camus",       "EN", "fiction"),
    ("The Fall",                                "Albert Camus",       "EN", "fiction"),
    ("The Myth of Sisyphus",                    "Albert Camus",       "EN", "secondary"),
    # Nietzsche expansion
    ("Beyond Good and Evil",                    "Friedrich Nietzsche","EN", "primary"),
    ("Thus Spoke Zarathustra",                  "Friedrich Nietzsche","EN", "primary"),
    ("The Gay Science",                         "Friedrich Nietzsche","EN", "primary"),
    # Shakespeare expansion
    ("Hamlet",                                  "William Shakespeare","EN", "fiction"),
    ("King Lear",                               "William Shakespeare","EN", "fiction"),
    ("Othello",                                 "William Shakespeare","EN", "fiction"),
    # Hesse expansion
    ("The Glass Bead Game",                     "Herman Hesse",       "EN", "fiction"),
    ("Narcissus and Goldmund",                  "Herman Hesse",       "EN", "fiction"),
    ("Demian",                                  "Herman Hesse",       "EN", "fiction"),
    # Kafka (new author)
    ("The Trial",                               "Franz Kafka",        "EN", "fiction"),
    ("The Castle",                              "Franz Kafka",        "EN", "fiction"),
    ("The Metamorphosis",                       "Franz Kafka",        "EN", "fiction"),
    # Proust (new author)
    ("Swann's Way",                             "Marcel Proust",      "FR", "fiction"),
    ("In the Shadow of Young Girls in Flower",  "Marcel Proust",      "FR", "fiction"),
    ("The Guermantes Way",                      "Marcel Proust",      "FR", "fiction"),
    ("Sodom and Gomorrah",                      "Marcel Proust",      "FR", "fiction"),
    ("The Prisoner",                            "Marcel Proust",      "FR", "fiction"),
    ("The Fugitive",                            "Marcel Proust",      "FR", "fiction"),
    ("Time Regained",                           "Marcel Proust",      "FR", "fiction"),
    # Chekhov (new author)
    ("Three Sisters",                           "Anton Chekhov",      "EN", "fiction"),
    ("The Cherry Orchard",                      "Anton Chekhov",      "EN", "fiction"),
    ("Uncle Vanya",                             "Anton Chekhov",      "EN", "fiction"),
    ("Ward No. 6 and Other Stories",            "Anton Chekhov",      "EN", "fiction"),
    # Flaubert (new author)
    ("Madame Bovary",                           "Gustave Flaubert",   "FR", "fiction"),
    ("Sentimental Education",                   "Gustave Flaubert",   "EN", "fiction"),
]

# ---------------------------------------------------------------------------
# Streams  (name, description, color, direct-work [(title_substr, author_substr)])
# ---------------------------------------------------------------------------

STREAMS: list[dict] = [
    {
        "name": "Russian & Slavic Canon",
        "description": "Dostoyevsky, Tolstoy, Chekhov, Gogol, Turgenev — the great Russian tradition",
        "color": "#c0392b",
        "works": [
            # Works not covered by collections (standalone authors in this stream)
            ("Dead Souls",          "Gogol"),
            ("Short Stories",       "Gogol"),
            ("Fathers and Sons",    "Turgenev"),
            ("A hero of our time",  "Lermontov"),
            ("Doctor Zhivago",      "Pasternak"),
            ("De Bouwput",          "Platonov"),
            ("De Kapiteinsdochter", "Pushkin"),
            # Chekhov
            ("Three Sisters",       "Chekhov"),
            ("Cherry Orchard",      "Chekhov"),
            ("Uncle Vanya",         "Chekhov"),
            ("Ward No. 6",          "Chekhov"),
        ],
    },
    {
        "name": "Japanese Modernism",
        "description": "Mishima, Dazai, Soseki, Kawabata — 20th-century Japanese prose",
        "color": "#e74c3c",
        "works": [
            # Mishima covered by collections; standalone:
            ("No Longer Human",  "Dazai"),
            ("The Miner",        "Soseki"),
            ("Kokoro",           "Soseki"),
        ],
    },
    {
        "name": "Flemish Letters",
        "description": "Buysse, Streuvels, Claus, Elsschot, Couperus — Flemish & Dutch prose",
        "color": "#f39c12",
        "works": [
            # Buysse covered by collections; standalone:
            ("De Vlaschaard",              "Streuvels"),
            ("leven en dood in den ast",   "Streuvels"),
            ("Lijmen",                     "Elsschot"),
            ("Het Verdriet van België",    "Claus"),
            ("Van oude mensen",            "Couperus"),
        ],
    },
    {
        "name": "Ancient & Classical",
        "description": "Plato, Sophocles, Aristotle — the Greek foundation",
        "color": "#8e44ad",
        "works": [
            # Plato covered by collections; standalone:
            ("Antigone",    "Sophocles"),
        ],
    },
    {
        "name": "Modern Philosophy",
        "description": "Descartes, Hume, Leibniz, Nietzsche — Western philosophy 1600–present",
        "color": "#2980b9",
        "works": [
            # Nietzsche + Kenny covered by collections; standalone:
            ("Meditations on First Philosophy", "Descartes"),
            ("An Enquiry",                      "Hume"),
            ("Discourse on Metaphysics",        "Leibniz"),
            ("Nietzsche: Philosopher",          "Kaufmann"),
            ("Man and his Symbols",             "Jung"),
        ],
    },
    {
        "name": "Political & Social Thought",
        "description": "Machiavelli, More, Hoffer, Kaczynski, Graeber, Thiel",
        "color": "#16a085",
        "works": [
            ("The Prince",                        "Machiavelli"),
            ("Utopia",                            "More"),
            ("The True Believer",                 "Hoffer"),
            ("Industrial Society and its Future", "Kaczynski"),
            ("Bullshit Jobs",                     "Graeber"),
            ("Zero to One",                       "Thiel"),
        ],
    },
    {
        "name": "French Literature",
        "description": "Proust, Balzac, Stendhal, Camus, Flaubert, Gide, Bataille",
        "color": "#3498db",
        "works": [
            # Camus + Stendhal + Proust + Flaubert covered by collections; standalone:
            ("Le Père Goriot",   "Balzac"),
            ("immoraliste",      "Gide"),
            ("Story of the Eye", "Bataille"),
        ],
    },
    {
        "name": "German & Central European",
        "description": "Kafka, Hesse, Mann, Zweig — Germanic modernism",
        "color": "#7f8c8d",
        "works": [
            # Kafka + Hesse covered by collections; standalone:
            ("De Toverberg",          "Mann"),
            ("The World of Yesterday","Zweig"),
        ],
    },
    {
        "name": "Buddhist & Asian Studies",
        "description": "Art history, Buddhist thought, Tibetan studies",
        "color": "#e67e22",
        "works": [
            ("Tibetan Art",                "Heller"),
            ("Chola: Sacred Bronzes",      "Deheija"),
            ("Adoration & Glory",          "Bunker"),
            ("Buddhist Thought",           "Williams"),
            ("Buddhist Ritual Art",        "Henss"),
            ("The Sacred and the Profane", "Eliade"),
        ],
    },
    {
        "name": "English & American Fiction",
        "description": "Shakespeare, Hardy, Waugh, Nabokov, Conrad, Wilde — Anglophone canon",
        "color": "#27ae60",
        "works": [
            # Shakespeare covered by collection; standalone:
            ("Heart of Darkness",       "Conrad"),
            ("Lolita",                  "Nabokov"),
            ("Picture of Dorian Gray",  "Wilde"),
            ("American Psycho",         "Ellis"),
            ("Jude The Obscure",        "Hardy"),
            ("Decline and Fall",        "Waugh"),
            ("Black Mischief",          "Waugh"),
            ("Brave New World",         "Huxley"),
            ("Catcher in the Rye",      "Salinger"),
            ("A shadow out of Time",    "Lovecraft"),
        ],
    },
]

# ---------------------------------------------------------------------------
# Collections  (type, author_name for author_id lookup, works)
# Works: (title_substr, author_substr) for unordered,
#        (title_substr, author_substr, order) for series
# ---------------------------------------------------------------------------

COLLECTIONS: list[dict] = [
    # ---- Major Works ----
    {
        "name": "Dostoyevsky — Major Works",
        "type": "major_works",
        "author_name": "Fyodor Dostoyevsky",
        "description": "The four great novels and essential long fiction",
        "works": [
            ("Crime and Punishment",       "Dostoyevsky"),
            ("The Idiot",                  "Dostoyevsky"),
            ("The Brothers Karamazov",     "Dostoyevsky"),
            ("Notes from the Underground", "Dostoyevsky"),
            ("The Demons",                 "Dostoyevsky"),
            ("The Adolescent",             "Dostoyevsky"),
        ],
    },
    {
        "name": "Dostoyevsky — Minor Works",
        "type": "minor_works",
        "author_name": "Fyodor Dostoyevsky",
        "description": "Novellas and short fiction",
        "works": [
            ("Bobok",        "Dostoyevsky"),
            ("White Nights", "Dostoyevsky"),
            ("Short Stories","Dostoevsky"),
            ("Poor Folk",    "Dostoyevsky"),
            ("Gambler",      "Dostoyevsky"),
        ],
    },
    {
        "name": "Tolstoy — Major Works",
        "type": "major_works",
        "author_name": "Leo Tolstoy",
        "description": "The great novels and essential shorter fiction",
        "works": [
            ("Anna Karenina",       "Tolstoy"),
            ("War and Peace",       "Tolstoy"),
            ("Death of Ivan Ilyich","Tolstoy"),
            ("Kreutzer Sonata",     "Tolstoy"),
        ],
    },
    {
        "name": "Mishima — Major Works",
        "type": "major_works",
        "author_name": "Yukio Mishima",
        "description": "Mishima's major novels",
        "works": [
            ("Spring Snow",                    "Mishima"),
            ("Runaway Horses",                 "Mishima"),
            ("Temple of Dawn",                 "Mishima"),
            ("Decay of the Angel",             "Mishima"),
            ("Confessions of a Mask",          "Mishima"),
            ("Sailor who Fell",                "Mishima"),
            ("Temple of the Golden Pavilion",  "Mishima"),
        ],
    },
    {
        "name": "Plato — Major Works",
        "type": "major_works",
        "author_name": "Plato",
        "description": "The canonical dialogues",
        "works": [
            ("Symposium", "Plato"),
            ("Phaedrus",  "Plato"),
            ("Apologia",  "Plato"),
            ("Republic",  "Plato"),
            ("Phaedo",    "Plato"),
            ("Meno",      "Plato"),
        ],
    },
    {
        "name": "Plato — Minor Works",
        "type": "minor_works",
        "author_name": "Plato",
        "description": "Shorter dialogues",
        "works": [
            ("Crito", "Plato"),
        ],
    },
    {
        "name": "Camus — Major Works",
        "type": "major_works",
        "author_name": "Albert Camus",
        "description": "Camus's fiction and philosophical essays",
        "works": [
            ("The Stranger",       "Camus"),
            ("The Plague",         "Camus"),
            ("The Fall",           "Camus"),
            ("Myth of Sisyphus",   "Camus"),
        ],
    },
    {
        "name": "Nietzsche — Major Works",
        "type": "major_works",
        "author_name": "Friedrich Nietzsche",
        "description": "The principal philosophical works",
        "works": [
            ("Twilight of the Idols",    "Nietzsche"),
            ("Beyond Good and Evil",     "Nietzsche"),
            ("Thus Spoke Zarathustra",   "Nietzsche"),
            ("Gay Science",              "Nietzsche"),
        ],
    },
    {
        "name": "Shakespeare — Major Works",
        "type": "major_works",
        "author_name": "William Shakespeare",
        "description": "The essential tragedies and comedies",
        "works": [
            ("Macbeth",                 "Shakespeare"),
            ("Hamlet",                  "Shakespeare"),
            ("King Lear",               "Shakespeare"),
            ("Othello",                 "Shakespeare"),
            ("Midsummer Night's Dream", "Shakespeare"),
        ],
    },
    {
        "name": "Hesse — Major Works",
        "type": "major_works",
        "author_name": "Herman Hesse",
        "description": "Major novels of self-discovery and spiritual seeking",
        "works": [
            ("Siddhartha",           "Hesse"),
            ("Steppenwolf",          "Hesse"),
            ("Glass Bead Game",      "Hesse"),
            ("Narcissus and Goldmund","Hesse"),
            ("Demian",               "Hesse"),
        ],
    },
    {
        "name": "Buysse — Major Works",
        "type": "major_works",
        "author_name": "Cyriel Buysse",
        "description": "Principal novels of Flemish peasant life",
        "works": [
            ("Recht van de Sterkste", "Buysse"),
            ("Gezin Van Paemel",      "Buysse"),
        ],
    },
    {
        "name": "Buysse — Minor Works",
        "type": "minor_works",
        "author_name": "Cyriel Buysse",
        "description": "Shorter fiction and tales",
        "works": [
            ("Biezenstekker",  "Buysse"),
            ("Broeder en Zuster","Buysse"),
            ("Lente",          "Buysse"),
        ],
    },
    {
        "name": "Stendhal — Major Works",
        "type": "major_works",
        "author_name": "Stendhal",
        "description": "The great novels",
        "works": [
            ("Rouge et le Noir", "Stendhal"),
        ],
    },
    {
        "name": "Kafka — Major Works",
        "type": "major_works",
        "author_name": "Franz Kafka",
        "description": "The three novels and essential novella",
        "works": [
            ("Trial",          "Kafka"),
            ("Castle",         "Kafka"),
            ("Metamorphosis",  "Kafka"),
        ],
    },
    {
        "name": "Flaubert — Major Works",
        "type": "major_works",
        "author_name": "Gustave Flaubert",
        "description": "The canonical realist novels",
        "works": [
            ("Madame Bovary",        "Flaubert"),
            ("Sentimental Education","Flaubert"),
        ],
    },
    # ---- Series ----
    {
        "name": "The Sea of Fertility",
        "type": "series",
        "author_name": "Yukio Mishima",
        "description": "Mishima's tetralogy: the reincarnation of the soul across four eras of Japan",
        "works": [
            ("Spring Snow",        "Mishima", 1),
            ("Runaway Horses",     "Mishima", 2),
            ("Temple of Dawn",     "Mishima", 3),
            ("Decay of the Angel", "Mishima", 4),
        ],
    },
    {
        "name": "Socratic Dialogues",
        "type": "series",
        "author_name": "Plato",
        "description": "Plato's dialogues centred on Socrates, in dramatic chronology",
        "works": [
            ("Apologia",  "Plato", 1),
            ("Crito",     "Plato", 2),
            ("Phaedo",    "Plato", 3),
            ("Phaedrus",  "Plato", 4),
            ("Symposium", "Plato", 5),
            ("Republic",  "Plato", 6),
            ("Meno",      "Plato", 7),
        ],
    },
    {
        "name": "Stendhal — Italian Chronicles",
        "type": "series",
        "author_name": "Stendhal",
        "description": "Short historical novellas set in Renaissance Italy",
        "works": [
            ("Abbesse de Castro", "Stendhal", 1),
            ("Vanina Vanini",     "Stendhal", 2),
        ],
    },
    {
        "name": "History of Western Philosophy",
        "type": "series",
        "author_name": "Anthony Kenny",
        "description": "Anthony Kenny's four-volume history of Western philosophy",
        "works": [
            ("Ancient Philosophy",            "Kenny", 1),
            ("Rise of Modern Philosophy",     "Kenny", 2),
        ],
    },
    {
        "name": "À la Recherche du Temps Perdu",
        "type": "series",
        "author_name": "Marcel Proust",
        "description": "Proust's seven-volume masterwork: memory, time, and the self",
        "works": [
            ("Swann's Way",                   "Proust", 1),
            ("Shadow of Young Girls",         "Proust", 2),
            ("Guermantes Way",                "Proust", 3),
            ("Sodom and Gomorrah",            "Proust", 4),
            ("Prisoner",                      "Proust", 5),
            ("Fugitive",                      "Proust", 6),
            ("Time Regained",                 "Proust", 7),
        ],
    },
    {
        "name": "Cyriel Buysse — Village Stories",
        "type": "anthology",
        "author_name": "Cyriel Buysse",
        "description": "Buysse's portraits of Flemish rural life",
        "works": [
            ("Recht van de Sterkste", "Buysse", 1),
            ("Gezin Van Paemel",      "Buysse", 2),
            ("Biezenstekker",         "Buysse", 3),
            ("Broeder en Zuster",     "Buysse", 4),
        ],
    },
]

# ---------------------------------------------------------------------------
# Stream → collection assignments (IN_STREAM edges)
# ---------------------------------------------------------------------------

STREAM_COLLECTIONS: dict[str, list[str]] = {
    "Russian & Slavic Canon": [
        "Dostoyevsky — Major Works",
        "Dostoyevsky — Minor Works",
        "Tolstoy — Major Works",
    ],
    "Japanese Modernism": [
        "Mishima — Major Works",
        "The Sea of Fertility",
    ],
    "Flemish Letters": [
        "Buysse — Major Works",
        "Buysse — Minor Works",
        "Cyriel Buysse — Village Stories",
    ],
    "Ancient & Classical": [
        "Plato — Major Works",
        "Plato — Minor Works",
        "Socratic Dialogues",
    ],
    "Modern Philosophy": [
        "Nietzsche — Major Works",
        "History of Western Philosophy",
    ],
    "French Literature": [
        "Camus — Major Works",
        "Stendhal — Major Works",
        "Stendhal — Italian Chronicles",
        "À la Recherche du Temps Perdu",
        "Flaubert — Major Works",
    ],
    "German & Central European": [
        "Kafka — Major Works",
        "Hesse — Major Works",
    ],
    "English & American Fiction": [
        "Shakespeare — Major Works",
    ],
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    driver = build_driver(settings)
    async with driver.session() as s:

        # 1. Significance markings
        print("Setting significance on works…")
        sig_hits = 0
        for title, author_substr, sig in SIGNIFICANCE:
            res = await s.run(
                """
                MATCH (a:Author)-[:WROTE]->(w:Work)
                WHERE toLower(a.name) CONTAINS toLower($author)
                  AND toLower(w.title) CONTAINS toLower($title)
                SET w.significance = $sig
                RETURN count(w) AS n
                """,
                title=title, author=author_substr, sig=sig,
            )
            rec = await res.single()
            sig_hits += rec["n"] if rec else 0
        print(f"  {sig_hits} works marked")

        # 2. New authors
        print("Creating new authors…")
        for author_def in NEW_AUTHORS:
            aid = _author_id(author_def["name"])
            await s.run(
                """
                MERGE (a:Author {id: $id})
                ON CREATE SET a.name = $name,
                              a.birth_year = $birth_year,
                              a.death_year = $death_year,
                              a.nationality = $nationality,
                              a.primary_language = $primary_language
                """,
                id=aid,
                name=author_def["name"],
                birth_year=author_def.get("birth_year"),
                death_year=author_def.get("death_year"),
                nationality=author_def.get("nationality"),
                primary_language=author_def.get("primary_language"),
            )
        print(f"  {len(NEW_AUTHORS)} authors ensured")

        # 3. Expand author metadata for existing authors
        print("Enriching existing author metadata…")
        AUTHOR_META: list[dict] = [
            {"name": "Fyodor Dostoyevsky",  "birth_year": 1821, "death_year": 1881, "nationality": "Russian", "primary_language": "RU"},
            {"name": "Leo Tolstoy",          "birth_year": 1828, "death_year": 1910, "nationality": "Russian", "primary_language": "RU"},
            {"name": "Lev Tolstoy",          "birth_year": 1828, "death_year": 1910, "nationality": "Russian", "primary_language": "RU"},
            {"name": "Yukio Mishima",        "birth_year": 1925, "death_year": 1970, "nationality": "Japanese","primary_language": "JP"},
            {"name": "Plato",                "birth_year": -427,  "death_year": -347,  "nationality": "Greek",   "primary_language": "GR"},
            {"name": "Albert Camus",         "birth_year": 1913, "death_year": 1960, "nationality": "French",  "primary_language": "FR"},
            {"name": "Friedrich Nietzsche",  "birth_year": 1844, "death_year": 1900, "nationality": "German",  "primary_language": "DE"},
            {"name": "William Shakespeare",  "birth_year": 1564, "death_year": 1616, "nationality": "English", "primary_language": "EN"},
            {"name": "Herman Hesse",         "birth_year": 1877, "death_year": 1962, "nationality": "German",  "primary_language": "DE"},
            {"name": "Cyriel Buysse",        "birth_year": 1859, "death_year": 1932, "nationality": "Belgian", "primary_language": "NL"},
            {"name": "Stijn Streuvels",      "birth_year": 1871, "death_year": 1969, "nationality": "Belgian", "primary_language": "NL"},
            {"name": "Stendhal",             "birth_year": 1783, "death_year": 1842, "nationality": "French",  "primary_language": "FR"},
            {"name": "Honoré De Balzac",     "birth_year": 1799, "death_year": 1850, "nationality": "French",  "primary_language": "FR"},
            {"name": "Nikolai Gogol",        "birth_year": 1809, "death_year": 1852, "nationality": "Russian", "primary_language": "RU"},
            {"name": "Osamu Dazai",          "birth_year": 1909, "death_year": 1948, "nationality": "Japanese","primary_language": "JP"},
            {"name": "Natsume Soseki",       "birth_year": 1867, "death_year": 1916, "nationality": "Japanese","primary_language": "JP"},
            {"name": "Anthony Kenny",        "birth_year": 1931, "death_year": 2022, "nationality": "English", "primary_language": "EN"},
            {"name": "Thomas Mann",          "birth_year": 1875, "death_year": 1955, "nationality": "German",  "primary_language": "DE"},
            {"name": "Stefan Zweig",         "birth_year": 1881, "death_year": 1942, "nationality": "Austrian","primary_language": "DE"},
            {"name": "Milan Kundera",        "birth_year": 1929, "death_year": 2023, "nationality": "Czech",   "primary_language": "CZ"},
            {"name": "Hugo Claus",           "birth_year": 1929, "death_year": 2008, "nationality": "Belgian", "primary_language": "NL"},
            {"name": "Ivan Turgenev",        "birth_year": 1818, "death_year": 1883, "nationality": "Russian", "primary_language": "RU"},
            {"name": "Boris Pasternak",      "birth_year": 1890, "death_year": 1960, "nationality": "Russian", "primary_language": "RU"},
            {"name": "Vladimir Nabokov",     "birth_year": 1899, "death_year": 1977, "nationality": "Russian", "primary_language": "EN"},
            {"name": "Oscar Wilde",          "birth_year": 1854, "death_year": 1900, "nationality": "Irish",   "primary_language": "EN"},
        ]
        for am in AUTHOR_META:
            await s.run(
                """
                MATCH (a:Author {id: $id})
                SET a.birth_year = coalesce(a.birth_year, $birth_year),
                    a.death_year = coalesce(a.death_year, $death_year),
                    a.nationality = coalesce(a.nationality, $nationality),
                    a.primary_language = coalesce(a.primary_language, $primary_language)
                """,
                id=_author_id(am["name"]),
                birth_year=am.get("birth_year"),
                death_year=am.get("death_year"),
                nationality=am.get("nationality"),
                primary_language=am.get("primary_language"),
            )
        print(f"  {len(AUTHOR_META)} authors enriched")

        # 4. New works
        print("Creating new works…")
        work_count = 0
        for title, author_name, lang, src_type in NEW_WORKS:
            aid = _author_id(author_name)
            wid = _work_id(title, author_name)
            await s.run(
                """
                MERGE (w:Work {id: $id})
                ON CREATE SET w.title = $title,
                              w.status = 'to_read',
                              w.language_read_in = $lang,
                              w.source_type = $src_type
                """,
                id=wid, title=title, lang=lang, src_type=src_type,
            )
            await s.run(
                """
                MATCH (a:Author {id: $aid})
                MATCH (w:Work   {id: $wid})
                MERGE (a)-[:WROTE]->(w)
                """,
                aid=aid, wid=wid,
            )
            work_count += 1
        print(f"  {work_count} works ensured")

        # 5. Streams
        print("Creating streams…")
        stream_id_map: dict[str, str] = {}
        for stream_def in STREAMS:
            sid = _stream_id(stream_def["name"])
            stream_id_map[stream_def["name"]] = sid
            await s.run(
                """
                MERGE (st:Stream {id: $id})
                ON CREATE SET st.name = $name, st.description = $description,
                              st.color = $color, st.created_at = toString(datetime())
                ON MATCH  SET st.name = $name, st.description = $description,
                              st.color = $color
                """,
                id=sid, name=stream_def["name"],
                description=stream_def["description"], color=stream_def["color"],
            )
            assigned = 0
            for title, author_substr in stream_def["works"]:
                res = await s.run(
                    """
                    MATCH (a:Author)-[:WROTE]->(w:Work)
                    WHERE toLower(a.name) CONTAINS toLower($author)
                      AND toLower(w.title) CONTAINS toLower($title)
                    MATCH (st:Stream {id: $stream_id})
                    MERGE (w)-[r:BELONGS_TO]->(st)
                    ON CREATE SET r.position = $pos
                    RETURN count(r) AS n
                    """,
                    title=title, author=author_substr,
                    stream_id=sid, pos=assigned + 1,
                )
                rec = await res.single()
                n = rec["n"] if rec else 0
                assigned += n
            print(f"  {stream_def['name']}: {assigned} direct works")

        # 6. Collections — MERGE author_id from existing Author node
        print("Creating collections…")
        coll_id_map: dict[str, str] = {}
        for coll_def in COLLECTIONS:
            cid = _coll_id(coll_def["name"])
            coll_id_map[coll_def["name"]] = cid

            # Resolve author_id from DB
            author_res = await s.run(
                "MATCH (a:Author) WHERE toLower(a.name) CONTAINS toLower($name) RETURN a.id AS id LIMIT 1",
                name=coll_def["author_name"],
            )
            author_rec = await author_res.single()
            author_id = author_rec["id"] if author_rec else None

            await s.run(
                """
                MERGE (c:Collection {id: $id})
                ON CREATE SET c.name = $name, c.description = $description,
                              c.type = $type,  c.author_id = $author_id
                ON MATCH  SET c.name = $name, c.description = $description,
                              c.type = $type,  c.author_id = $author_id
                """,
                id=cid, name=coll_def["name"], description=coll_def.get("description"),
                type=coll_def["type"], author_id=author_id,
            )

            # Assign works to collection
            works = coll_def.get("works", [])
            assigned = 0
            for entry in works:
                if len(entry) == 3:
                    title, author_substr, order = entry
                else:
                    title, author_substr = entry
                    order = None
                res = await s.run(
                    """
                    MATCH (a:Author)-[:WROTE]->(w:Work)
                    WHERE toLower(a.name) CONTAINS toLower($author)
                      AND toLower(w.title) CONTAINS toLower($title)
                    MATCH (c:Collection {id: $cid})
                    MERGE (w)-[r:IN_COLLECTION]->(c)
                    SET r.order = $order
                    RETURN count(r) AS n
                    """,
                    title=title, author=author_substr, cid=cid, order=order,
                )
                rec = await res.single()
                assigned += rec["n"] if rec else 0
            print(f"  {coll_def['name']}: {assigned} works assigned")

        # 7. Collection → Stream assignments (IN_STREAM edges)
        print("Linking collections to streams…")
        for stream_name, coll_names in STREAM_COLLECTIONS.items():
            sid = stream_id_map.get(stream_name)
            if not sid:
                print(f"  WARNING: stream '{stream_name}' not found, skipping")
                continue
            for i, coll_name in enumerate(coll_names):
                cid = coll_id_map.get(coll_name)
                if not cid:
                    print(f"  WARNING: collection '{coll_name}' not found, skipping")
                    continue
                await s.run(
                    """
                    MATCH (c:Collection {id: $cid})
                    MATCH (st:Stream    {id: $sid})
                    MERGE (c)-[r:IN_STREAM]->(st)
                    SET r.order = $order
                    """,
                    cid=cid, sid=sid, order=i + 1,
                )
            print(f"  {stream_name}: {len(coll_names)} collections linked")

    await driver.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
