"""Diplomacy: what the realms think of each other, and what they can ask of each other.

Opinion runs from -100 to 100. Faith, old friendships and feuds, shared borders and recent wars set
where it settles; gifts and envoys move it for a while. Alliances bring allies into defensive wars; a
much weaker neighbour may agree to pay tribute rather than fight.
"""

CHRISTIAN = {"catholic", "orthodox", "bosnian_church", "armenian"}
RELATION_OPINION = {"alliance": 40, "union": 60, "marriage": 25, "rivalry": -40, "war": -60}
MAX_ALLIANCES = 3
GIFT_OPINION = 25          # for a gift of a month of the receiver's income
TRUCE_GRUDGE = -30


class Diplomacy:
    """The realms' feelings and dealings (part of Campaign)."""

    def _init_diplomacy(self):
        self.opinions = {}        # "a|b" -> how a and b regard each other
        self.grudges = {}         # "a|b" -> a passing modifier that fades
        self._neighbours = None
        self._history = {}
        for rel in self.relations:
            a, b = rel["tags"]
            self._history[_key(a, b)] = self._history.get(_key(a, b), 0) + RELATION_OPINION.get(rel["kind"], 0)
        for a in self.realms:
            for b in self.realms:
                if a < b:
                    self.opinions[_key(a, b)] = self.base_opinion(a, b)

    @property
    def neighbours(self):
        """{realm: set of realms whose land touches its own} (recomputed when borders change)."""
        if self._neighbours is None:
            out = {t: set() for t in self.realms}
            for p in self.provinces.values():
                for n in self.static(p.id).neighbors:
                    other = self.provinces[n].owner
                    if other != p.owner:
                        out[p.owner].add(other)
            self._neighbours = out
        return self._neighbours

    def borders_changed(self):
        self._neighbours = None

    def base_opinion(self, a, b):
        ra, rb = self.info[a]["religion"], self.info[b]["religion"]
        if ra == rb:
            opinion = 10
        elif ra in CHRISTIAN and rb in CHRISTIAN:
            opinion = -5
        else:
            opinion = -25
        opinion += self._history.get(_key(a, b), 0)
        la, lb = self.overlord.get(a), self.overlord.get(b)
        if (la and la[0] == b) or (lb and lb[0] == a):
            opinion += 10
        if b in self.neighbours.get(a, ()):
            opinion -= 5
        if self.at_war(a, b):
            opinion -= 50
        if sorted((a, b)) in self.alliances:
            opinion += 15
        opinion += min(30, 15 * self.marriages.count(sorted((a, b))))
        opinion += (self.ruler_charm(a) + self.ruler_charm(b)) / 2
        return max(-100, min(100, opinion + self.grudges.get(_key(a, b), 0)))

    def opinion(self, a, b):
        if a == b:
            return 100
        return self.opinions.get(_key(a, b), 0)

    def diplomacy_month(self):
        """Opinions drift towards where they settle; grudges and favours fade."""
        for k in list(self.grudges):
            self.grudges[k] *= 0.95
            if abs(self.grudges[k]) < 1:
                del self.grudges[k]
        tags = [t for t in self.realms if self.realms[t].alive]
        for i, a in enumerate(tags):
            for b in tags[i + 1:]:
                k = _key(a, b)
                now = self.opinions.get(k, 0)
                self.opinions[k] = now + (self.base_opinion(a, b) - now) * 0.15

    def nudge(self, a, b, amount):
        """A lasting but fading change in how a and b regard each other."""
        k = _key(a, b)
        self.grudges[k] = max(-80, min(80, self.grudges.get(k, 0) + amount))
        self.opinions[k] = max(-100, min(100, self.opinions.get(k, 0) + amount))

    # --- what a realm can ask -----------------------------------------------------------------------

    def military_power(self, tag):
        """What a realm can put in the field: its armies, and a little of the men it could still call."""
        armies = sum(self.strength(a, "plains", False) for a in self.armies_of(tag))
        return armies + self.realms[tag].manpower / 100.0 * 4.0

    def coalition_power(self, defender, attacker):
        """The power that would answer an attack on `defender`."""
        return self.military_power(defender) + 0.7 * sum(self.military_power(t)
                                                         for t in self.defenders_called(defender, attacker))

    def alliance_answer(self, asker, asked):
        """(yes, why) for an offer of alliance."""
        if sorted((asker, asked)) in self.alliances:
            return False, "We are already allies."
        if self.at_war(asker, asked):
            return False, "We are at war."
        if len(self.allies_of(asked)) >= MAX_ALLIANCES:
            return False, f"{self.name(asked)} has allies enough."
        common = self.enemies_of(asker) & self.enemies_of(asked)
        threshold = 20 if common else 35
        if self.opinion(asker, asked) < threshold:
            return False, f"{self.name(asked)} does not trust us enough."
        return True, f"{self.name(asked)} agrees."

    def ally(self, a, b):
        ok, why = self.alliance_answer(a, b)
        if ok:
            self.alliances.append(sorted((a, b)))
            self.tell(a, f"Alliance sealed with {self.name(b)}.")
            self.tell(b, f"Alliance sealed with {self.name(a)}.")
        return ok, why

    def break_alliance(self, a, b):
        pair = sorted((a, b))
        if pair in self.alliances:
            self.alliances.remove(pair)
            self.nudge(a, b, -30)
            self.tell(b, f"{self.name(a)} has broken our alliance.")
            return True
        return False

    def tribute_answer(self, asker, asked):
        """Would `asked` rather pay tribute than face `asker` in war?"""
        if self.overlord.get(asked):
            return False, f"{self.name(asked)} already answers to {self.name(self.overlord[asked][0])}."
        if self.at_war(asker, asked):
            return False, "Not while we are at war."
        ratio = self.military_power(asker) / max(1.0, self.coalition_power(asked, asker))
        if ratio < 3.0:
            return False, f"{self.name(asked)} would rather fight."
        if self.opinion(asker, asked) < -30:
            return False, f"{self.name(asked)} hates us too much to bow."
        return True, f"{self.name(asked)} bows and will pay tribute."

    def demand_tribute(self, asker, asked):
        ok, why = self.tribute_answer(asker, asked)
        if ok:
            self.overlord[asked] = (asker, "tributary")
            self.tell(asker, why)
            self.tell(asked, f"We now pay tribute to {self.name(asker)}.")
        else:
            self.nudge(asker, asked, -10)
        return ok, why

    def send_gift(self, giver, taker, ducats):
        if ducats <= 0 or self.realms[giver].treasury < ducats:
            return False
        self.realms[giver].treasury -= ducats
        self.realms[taker].treasury += ducats
        worth = ducats / max(100.0, self.budget(taker).income)
        self.nudge(giver, taker, min(40.0, GIFT_OPINION * worth))
        self.tell(taker, f"{self.name(giver)} sends us {ducats:,.0f} ducats.")
        return True


def _key(a, b):
    return "|".join(sorted((a, b)))
