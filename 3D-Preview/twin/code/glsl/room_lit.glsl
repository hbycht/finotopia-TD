// room_lit - Raum- und Fixture-Koerper, beleuchtet von beliebig vielen Lichtern.
// Lichtdaten kommen als Texture Buffer aus dem Script CHOP 'lights' (ein Sample je Licht):
//   uLPos: xyz Position, w kind (0 = Spot, 1 = Punkt)
//   uLDir: xyz Richtung, w cos(Aussenwinkel) (Spot) bzw. Falloff-Faktor (Punkt)
//   uLCol: rgb Farbe * Intensitaet, w cos(Innenwinkel)
// Kein Light COMP, daher kein 8-Lichter-Limit. Albedo = Vertexfarbe (aus room.ply / meshes/*.ply).

uniform samplerBuffer uLPos;
uniform samplerBuffer uLDir;
uniform samplerBuffer uLCol;
uniform float uNumLights;
uniform float uAmbient;
uniform float uFalloff;
uniform float uLightGain;

#ifdef TD_VERTEX_SHADER
out Vert {
    vec4 color;
    vec3 worldPos;
    flat int cameraIndex;
} oVert;

void main()
{
    oVert.color = TDInstanceColor(TDPointColor());
    vec4 worldPos = TDDeform(TDPos());
    oVert.worldPos = worldPos.xyz;
    oVert.cameraIndex = TDCameraIndex();
    gl_Position = TDWorldToProj(worldPos);
}
#endif

#ifdef TD_PIXEL_SHADER
in Vert {
    vec4 color;
    vec3 worldPos;
    flat int cameraIndex;
} iVert;

layout(location = 0) out vec4 oFragColor[TD_NUM_COLOR_BUFFERS];

void main()
{
    TDCheckDiscard();
    vec3 P = iVert.worldPos;
    // flache Normale aus den Bildschirm-Ableitungen, zur Kamera gedreht
    vec3 N = normalize(cross(dFdx(P), dFdy(P)));
    vec3 camPos = uTDMats[iVert.cameraIndex].camInverse[3].xyz;
    if (dot(N, camPos - P) < 0.0)
        N = -N;

    vec3 light = vec3(uAmbient);
    int numLights = int(uNumLights);
    for (int i = 0; i < numLights; i++) {
        vec4 lp = texelFetch(uLPos, i);
        vec4 ld = texelFetch(uLDir, i);
        vec4 lc = texelFetch(uLCol, i);
        vec3 L = lp.xyz - P;
        float d2 = max(dot(L, L), 1e-4);
        L *= inversesqrt(d2);
        float cone = 1.0;
        float fo = uFalloff;
        if (lp.w < 0.5)
            cone = smoothstep(ld.w, lc.w, dot(-L, normalize(ld.xyz)));
        else
            fo *= ld.w;
        float att = 1.0 / (1.0 + fo * d2);
        light += lc.rgb * uLightGain * max(dot(N, L), 0.0) * att * cone;
    }
    oFragColor[0] = TDOutputSwizzle(vec4(iVert.color.rgb * light, 1.0));
}
#endif
