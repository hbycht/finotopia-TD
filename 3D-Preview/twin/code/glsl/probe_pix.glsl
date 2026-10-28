// probe_pix - tastet die Pixel-Maps an allen LED-Pixeln ab (Ausstellungsmodus des Twins).
// Ersetzt col_out der node*-Pixel-Fixtures: gleiche Punkte (geo_out), gleiche UV-Normierung,
// Master + 8-bit-Rundung wie math1, W-Kanal = Mittelwert * White wie math3.
// Ausgabe: Breite = Anzahl Pixel, Hoehe 1, rgb = Farbe (W bereits auf RGB addiert).
//
// Inputs (verdrahtet in /project1): 0 map_Blinder, 1 map_Panel, 2 map_Penta  (Reihenfolge = twin_lib.pixel_maps)
// Arrays (Texture Buffer aus VISUAL_PREVIEW/twin/probe_pix_tab):
//   uTabA: u, v, src, gain(Master)      uTabB: white, -, -, -

uniform samplerBuffer uTabA;
uniform samplerBuffer uTabB;

layout(location = 0) out vec4 fragColor;

vec3 SampleMap(int src, vec2 uv)
{
    if (src == 0)
        return texture(sTD2DInputs[0], uv).rgb;
    if (src == 1)
        return texture(sTD2DInputs[1], uv).rgb;
    return texture(sTD2DInputs[2], uv).rgb;
}

void main()
{
    int i = int(gl_FragCoord.x);
    vec4 a = texelFetch(uTabA, i);
    vec4 b = texelFetch(uTabB, i);
    vec3 c = SampleMap(int(a.z + 0.5), a.xy);
    float w = (c.r + c.g + c.b) / 3.0 * b.x;
    c = floor(clamp(c + w, 0.0, 1.0) * a.w * 255.0 + 0.5) / 255.0;
    fragColor = TDOutputSwizzle(vec4(c, 1.0));
}
