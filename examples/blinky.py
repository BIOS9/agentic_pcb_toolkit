"""A 555 astable blinking an LED.

The fast CI smoke test: small enough to build in under a second, but it still
exercises hierarchy, global rails, a named local net, positional and by-name pin
connection, and constraints.
"""

from pcbkit.dsl import C, Gnd, J, LED, Net, Part, Power, R, design, module, rule


@module
def power_in(vcc, gnd):
    """Barrel jack with reverse-protection diode and bulk capacitance."""
    jack = J("Barrel_Jack", pkg="BarrelJack_Horizontal")
    raw = Net("VRAW")
    jack[1] >> raw
    jack[2] >> gnd

    protect = Part("SS34", prefix="D", pkg="SMA")
    raw >> protect.A
    protect.K >> vcc

    bulk = C("100uF", pkg="Elec_6.3x5.4")
    bulk(vcc, gnd)
    rule.edge(jack, side="left")
    rule.current(vcc, amps=0.1)


@module
def astable(vcc, gnd, out):
    """NE555 astable, roughly 1 Hz at 50% duty."""
    timer = Part("NE555", prefix="U", pkg="SOIC-8")

    timer.VCC >> vcc
    timer.GND >> gnd
    timer.RESET >> vcc

    r_charge = R("10k", pkg="0603")
    r_discharge = R("68k", pkg="0603")
    timing = C("10uF", pkg="0805")

    trigger = Net("TRIG")
    discharge = Net("DISCH")

    r_charge(vcc, discharge)
    r_discharge[1] >> discharge
    r_discharge[2] >> trigger
    timing(trigger, gnd)

    timer.DISCH >> discharge
    timer.TRIG >> trigger
    timer.THRES >> trigger
    timer.OUT >> out

    # Pin 5 wants a bypass cap to keep the internal divider quiet.
    control = C("10nF", pkg="0603")
    control[1] >> timer.CONT
    control[2] >> gnd

    rule.decouple(timer, max_mm=5)


@module
def indicator(signal, gnd):
    led = LED("red", pkg="0805")
    limit = R("1k", pkg="0603")
    signal >> led[1]
    led[2] >> limit[1]
    limit[2] >> gnd
    rule.near(led, limit, max_mm=4)


@design("blinky", width_mm=30, height_mm=20, layers=2)
def blinky():
    vcc = Power("+5V", 5.0)
    gnd = Gnd()
    blink = Net("BLINK")

    power_in(vcc, gnd)
    astable(vcc, gnd, blink)
    indicator(blink, gnd)
