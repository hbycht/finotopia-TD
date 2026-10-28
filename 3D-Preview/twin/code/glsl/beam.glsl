// beam - volumetrischer Lichtkegel der Moving Heads (additiv, ohne Tiefenschreiben).
// Geometrie: meshes/beam.ply, Kegel mit Spitze im Ursprung, oeffnet nach -y (Laenge 1, Radius 1).
// Instancing: Position = Kopf, rotate-to-vector = Strahlrichtung, Scale = Radius/Laenge, Farbe = Beam-RGB*Dimmer.

uniform float uHaze;       // Dunstdichte (Grundwert + FOG-Kanal)
uniform float uBeamGain;   // Gesamthelligkeit der Beams
uniform float uEdge;       // Exponent fuer den Fresnel-Rand (hoeher = weicherer Kegel)

#ifdef TD_VERTEX_SHADER
out Vert {
    vec4 color;
    vec3 worldPos;
    vec3 worldNorm;
    float along;
    flat int cameraIndex;
} oVert;

void main()
{
    vec3 p = TDPos();
    oVert.along = clamp(-p.y, 0.0, 1.0);
    // analytische Kegelnormale (x^2 + z^2 = y^2), vermeidet das N-Attribut der POP-Geometrie
    vec3 nLocal = normalize(vec3(p.x, -p.y, p.z) + vec3(0.0, 1e-5, 0.0));
    oVert.worldNorm = normalize(TDDeformNorm(nLocal));
    oVert.color = TDInstanceColor(vec4(1.0));
    vec4 worldPos = TDDeform(p);
    oVert.worldPos = worldPos.xyz;
    oVert.cameraIndex = TDCameraIndex();
    gl_Position = TDWorldToProj(worldPos);
}
#endif

#ifdef TD_PIXEL_SHADER
in Vert {
    vec4 color;
    vec3 worldPos;
    vec3 worldNorm;
    float along;
    flat int cameraIndex;
} iVert;

layout(location = 0) out vec4 oFragColor[TD_NUM_COLOR_BUFFERS];

void main()
{
    TDCheckDiscard();
    vec3 camPos = uTDMats[iVert.cameraIndex].camInverse[3].xyz;
    vec3 V = normalize(camPos - iVert.worldPos);
    vec3 N = normalize(iVert.worldNorm);
    float facing = abs(dot(N, V));              // 1 = Kegelmitte, 0 = Silhouette
    // Kegel als Volumen: Mitte heller, Rand weich, plus ein schwacher Grundschleier ueber die ganze Breite
    float core = 0.25 + 0.75 * pow(facing, uEdge);
    float fall = pow(1.0 - iVert.along, 1.2);   // Abfall entlang des Strahls
    float start = smoothstep(0.0, 0.015, iVert.along);
    vec3 c = iVert.color.rgb * core * fall * start * uHaze * uBeamGain;
    oFragColor[0] = TDOutputSwizzle(vec4(c, 0.0));
}
#endif
