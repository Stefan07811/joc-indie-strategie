"""Crusades against the Turk, and the end of the chronicle.

When the Ottomans grow, the Pope preaches a crusade: the strongest Catholic realm on their border leads
it, and the Christian princes are called to join (the player with a choice, the others as their interests
and tempers say). The chronicle closes in 1500 with a reckoning of the realms; a realm that falls before
that closes it early for its player. Mixed into Campaign."""

from .calendar import Date

CRUSADE_EVERY = 120          # months between crusades at the least
FIRST_CRUSADE = Date(1404, 1)
END = Date(1500, 1)
CHRISTIAN = ("catholic", "orthodox")


def ottomans(c):
    return [t for t in c.realms if t.startswith("ott_") and c.realms[t].alive]


class Crusades:
    def _init_crusades(self):
        self.crusade = None          # {"war": id, "leader": tag, "target": tag, "since": [y, m]}
        self.last_crusade = None     # [y, m]
        self.ottoman_start = self.ottoman_holdings()
        self.ended = False

    def ottoman_holdings(self):
        return sum(1 for p in self.provinces.values() if p.owner.startswith("ott_"))

    def religion(self, tag):
        return self.info[tag].get("religion", "")

    # --- the crusade --------------------------------------------------------------------------------

    def crusade_month(self):
        if self.crusade is not None:
            if not any(w.id == self.crusade["war"] for w in self.wars):
                self.tell(self.player, "The crusade is over.")
                self.crusade = None
            return
        if self.date < FIRST_CRUSADE or "papal" not in self.realms or not self.realms["papal"].alive:
            return
        if self.last_crusade and self.date.months_since(Date(*self.last_crusade)) < CRUSADE_EVERY:
            return
        growth = self.ottoman_holdings() - self.ottoman_start
        chance = 0.004 + 0.006 * max(0, growth)
        if self.rng.random() < chance:
            self.call_crusade()

    def call_crusade(self):
        """The Pope preaches the crusade; returns the war, or None if no one could lead it."""
        targets = ottomans(self)
        if not targets:
            return None
        target = max(targets, key=lambda t: len(self.provinces_of(t)))
        leaders = [t for t in self.realms if self.realms[t].alive and self.religion(t) == "catholic" and
                   target in self.neighbours.get(t, ()) and not self.at_war(t, target) and
                   not self.overlord.get(t)]
        if not leaders:
            return None
        leader = max(leaders, key=self.military_power)
        border = [p.id for p in self.provinces_of(target)
                  if any(self.provinces[n].owner == leader for n in self.static(p.id).neighbors)]
        if not border:
            return None
        from .war import War
        goal = {"kind": "conquest", "province": max(border, key=self.value)}
        defenders = [target] + [t for t in self.defenders_called(target, exclude=leader) if t != leader]
        war = War(f"w{self._next_war}", [leader], defenders, goal, self.date)
        self._next_war += 1
        self.wars.append(war)
        war.log.append(f"{self.date}: the Pope preaches a crusade; {self.name(leader)} takes the cross.")
        self.crusade = {"war": war.id, "leader": leader, "target": target, "since": [self.date.year,
                                                                                   self.date.month]}
        self.last_crusade = [self.date.year, self.date.month]
        text = (f"The Pope preaches a crusade against {self.name(target)}! {self.name(leader)} takes the cross "
                "and calls the Christian princes to follow.")
        self.history.append([str(self.date), f"A crusade against {self.name(target)}"])
        self.tell(self.player, text)
        # the princes answer
        for tag in list(self.realms):
            if not self.crusade_invited(tag):
                continue
            if tag == self.player:
                from .history import EVENT
                self.fire(EVENT["crusade_call"], tag)
            elif self.rng.random() < (0.5 if self.religion(tag) == "catholic" else 0.3) * \
                    (1.0 + max(-0.8, self.opinion(tag, leader) / 100.0)):
                self.join_crusade(tag)
        return war

    def crusade_war(self):
        if self.crusade is None:
            return None
        return next((w for w in self.wars if w.id == self.crusade["war"]), None)

    def crusade_invited(self, tag):
        war = self.crusade_war()
        if war is None or not self.realms[tag].alive or tag in war.attackers or tag in war.defenders:
            return False
        if self.religion(tag) not in CHRISTIAN or self.at_war(tag, war.leader):
            return False
        lord = self.overlord.get(tag)
        if lord and lord[0] in war.defenders:
            return False               # the Sultan's own vassals do not march against him
        return self.crusade["target"] in self.neighbours.get(tag, ()) or \
            self.info[tag]["rank"] in ("kingdom", "empire")

    def join_crusade(self, tag):
        war = self.crusade_war()
        if war is None or tag in war.attackers:
            return
        war.attackers.append(tag)
        self.realms[tag].prestige += 10
        if "papal" in self.realms and self.realms["papal"].alive:     # the crusading tithe
            subsidy = min(600.0, max(0.0, self.realms["papal"].treasury * 0.1))
            self.realms["papal"].treasury -= subsidy
            self.realms[tag].treasury += subsidy
        war.log.append(f"{self.date}: {self.name(tag)} takes the cross.")
        self.tell(self.player, f"{self.name(tag)} joins the crusade.")

    def refuse_crusade(self, tag):
        self.realms[tag].prestige -= 5
        if "papal" in self.realms:
            self.nudge(tag, "papal", -15)

    # --- the end of the chronicle --------------------------------------------------------------------------

    def reckoning(self):
        """[(score, tag)] of the living realms, best first: land, prestige, wealth and vassals."""
        out = []
        for tag, r in self.realms.items():
            if not r.alive:
                continue
            vassals = sum(1 for v, held in self.overlord.items() if held and held[0] == tag and self.realms[v].alive)
            score = 10 * len(self.provinces_of(tag)) + r.prestige + max(0.0, r.treasury) / 1000 + 5 * vassals
            out.append((round(score), tag))
        out.sort(reverse=True)
        return out

    def chronicle_closes(self):
        """None while the game goes on; else why it ends for the player: "time" or "fallen"."""
        if self.ended or self.player is None:
            return None
        if not self.realms[self.player].alive:
            self.ended = True
            return "fallen"
        if self.date >= END:
            self.ended = True
            return "time"
        return None

    def crusades_to_dict(self):
        return {"crusade": self.crusade, "last": self.last_crusade, "ottoman_start": self.ottoman_start,
                "ended": self.ended}

    def crusades_from_dict(self, data):
        if not data:
            return
        self.crusade, self.last_crusade = data["crusade"], data["last"]
        self.ottoman_start, self.ended = data["ottoman_start"], data["ended"]
