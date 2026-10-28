// probe_ctrl - tastet die Steuerwerte fuer Moving Heads, Bulbs, Fog und die Pixel-Mittelwerte ab.
// Ersetzt die topto*-Abtastungen in den node*-Fixtures (Ausstellungsmodus des Twins).
// Die Vorfilter der Fixtures (Gauss-Blur nach Preshrink) werden ueber Mip-Level angenaehert,
// Bulbs/Fog zusaetzlich Monochrome (Luminanz) + Level (Brightness 1.1, Gamma 1.49).
// Ausgabe: Breite = Anzahl Probes, Hoehe 1, rgba.
//
// Inputs (verdrahtet in /project1): 0 map_Beams, 1 map_Rings, 2 MH_Move_Controller, 3 map_Bulbs,
//                                   4 map_Fog, 5 twin_probe_pix
// Arrays (Texture Buffer aus VISUAL_PREVIEW/twin/probe_ctrl_tab):
//   uTabA: u, v, src, start      uTabB: count, -, -, -
// src: 0 Beam, 1 Ring, 2 Movement, 3 Bulb, 4 Fog, 5 Mittelwert ueber probe_pix[start .. start+count)

uniform samplerBuffer uTabA;
uniform samplerBuffer uTabB;
uniform vec4 uLod;   // x: Beam/Ring/Fog, y: Movement, z: Bulbs

layout(location = 0) out vec4 fragColor;

vec4 Level(vec4 c)
{
    float m = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
    m = pow(clamp(m * 1.1, 0.0, 1.0), 1.0 / 1.49);
    return vec4(m, m, m, 1.0);
}

void main()
{
    int i = int(gl_FragCoord.x);
    vec4 a = texelFetch(uTabA, i);
    vec4 b = texelFetch(uTabB, i);
    int src = int(a.z + 0.5);
    vec2 uv = a.xy;
    vec4 o = vec4(0.0);
    if (src == 0)
        o = textureLod(sTD2DInputs[0], uv, uLod.x);
    else if (src == 1)
        o = textureLod(sTD2DInputs[1], uv, uLod.x);
    else if (src == 2)
        o = textureLod(sTD2DInputs[2], fract(uv), uLod.y);
    else if (src == 3)
        o = Level(textureLod(sTD2DInputs[3], uv, uLod.z));
    else if (src == 4)
        o = Level(textureLod(sTD2DInputs[4], uv, uLod.x));
    else {
        int start = int(a.w + 0.5);
        int n = int(b.x + 0.5);
        vec3 s = vec3(0.0);
        for (int k = 0; k < n; k++)
            s += texelFetch(sTD2DInputs[5], ivec2(start + k, 0), 0).rgb;
        o = vec4(s / max(float(n), 1.0), 1.0);
    }
    fragColor = TDOutputSwizzle(o);
}
