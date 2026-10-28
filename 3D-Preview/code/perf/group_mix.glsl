// group_mix - ersetzt pro Lichtgruppe die TOP-Ketten
//   ColorPicker_<G> (hsvadj1 Saettigung -> lookup1 independent mit Gradient-LUT)
//   -> dimmer_<G>   (switch1 Strobe-Blend -> level1 Master -> switch2 Flash-Blend mit level2(hsvadj3))
//   -> correction_<G> (Level RGBA 'High' = Kanal-Skalierung)
// durch einen einzigen GLSL TOP. Grund: auf dem Ausstellungs-Mac kostet jeder TOP ~0,4 ms CPU.
// Die Uniforms sind per Ausdruck an dieselben UI-CHOPs/Parameter gebunden wie die Original-Kette.
//
// Inputs: 0 Quelle (dim_ALL bzw. WHITE), 1 eigene Rampe (ColorPicker_<G>/ramp1), 2 globaler Gradient
//         (Gradientcomp/gradient). Auswahl wie ColorPicker_<G>/switch1 ueber uFlash.z.
//         Gruppen ohne ColorPicker haengen die Quelle an 1 und 2 (wird nicht gelesen).

uniform vec4 uState;   // x Saettigung, y Strobe-State, z Strobe-Phase, w Master-Fader
uniform vec4 uFlash;   // x Flash-State, y 1 = LUT verwenden (ColorPicker vorhanden), z LUT-Index (0 Rampe, 1 global)
uniform vec4 uHigh;    // rgb Correction High R/G/B

layout(location = 0) out vec4 fragColor;

vec3 RgbToHsv(vec3 c)
{
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
}

// 8-bit-Quantisierung wie die Original-TOPs (rgba8fixed)
vec3 Q8(vec3 c)
{
    return floor(clamp(c, 0.0, 1.0) * 255.0 + 0.5) / 255.0;
}

vec3 HsvToRgb(vec3 c)
{
    vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
    return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

void main()
{
    vec3 c = texture(sTD2DInputs[0], vUV.st).rgb;

    // ColorPicker: Saettigung, dann Gradient-LUT je Kanal (lookupTOP channel = independent, v = 0.5)
    if (uFlash.y > 0.5) {
        vec3 h = RgbToHsv(c);
        h.y = clamp(h.y * uState.x, 0.0, 1.0);
        c = HsvToRgb(h);
        // Lookup TOP adressiert von der ersten bis zur letzten Texelmitte
        if (uFlash.z < 0.5) {
            float w = float(textureSize(sTD2DInputs[1], 0).x);
            vec3 u = (clamp(c, 0.0, 1.0) * (w - 1.0) + 0.5) / w;
            c = vec3(texture(sTD2DInputs[1], vec2(u.r, 0.5)).r,
                     texture(sTD2DInputs[1], vec2(u.g, 0.5)).g,
                     texture(sTD2DInputs[1], vec2(u.b, 0.5)).b);
        } else {
            float w = float(textureSize(sTD2DInputs[2], 0).x);
            vec3 u = (clamp(c, 0.0, 1.0) * (w - 1.0) + 0.5) / w;
            c = vec3(texture(sTD2DInputs[2], vec2(u.r, 0.5)).r,
                     texture(sTD2DInputs[2], vec2(u.g, 0.5)).g,
                     texture(sTD2DInputs[2], vec2(u.b, 0.5)).b);
        }
    }

    c = Q8(c);   // Original-Kette arbeitet durchgehend in 8 bit

    // Strobe: switch1 blendet zum constant5 = Strobe-Phase * hsvadj1(Bild)
    // (hsvadjust 'Value Multiplier' wirkt in TD als Kanal-Multiplikation mit Klemmung)
    vec3 strobeImg = Q8(Q8(c * 5.0) * uState.z);
    vec3 s = Q8(mix(c, strobeImg, clamp(uState.y, 0.0, 1.0)));

    // Master (level1)
    vec3 m = Q8(s * uState.w);

    // Flash: hsvadj3 (Value * 30) -> level2 (Brightness 10), Blend ueber Flash-State (switch2)
    vec3 f = Q8(Q8(s * 30.0) * 10.0);
    vec3 o = Q8(mix(m, f, clamp(uFlash.x, 0.0, 1.0)));

    // Correction (Level RGBA High = Skalierung)
    o = Q8(o * uHigh.rgb);

    fragColor = TDOutputSwizzle(vec4(o, 1.0));
}
