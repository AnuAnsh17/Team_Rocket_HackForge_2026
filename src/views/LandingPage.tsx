import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import {
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  FileSearch,
  Scale,
  Lock,
  Layers,
  ChevronRight,
  ScanLine,
  RotateCcw,
} from 'lucide-react';
import { ActiveTab } from '../types';
import { Mini3DScene } from '../components/three/Mini3DScene';

interface LandingPageProps {
  onNavigate: (tab: ActiveTab) => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigate }) => {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [showRings, setShowRings] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);

  // Mutable state ref for 60fps Three.js animation loop without re-triggering React renders
  const stateRef = useRef({
    mouseX: 0,
    mouseY: 0,
    targetRotationX: 0.1,
    targetRotationY: -0.3,
    isScanning: false,
    scanProgress: 0,
    showRings: true,
    showBoxes: true,
  });

  useEffect(() => {
    stateRef.current.showRings = showRings;
    stateRef.current.showBoxes = showBoxes;
  }, [showRings, showBoxes]);

  // Three.js 3D Floating Receipt Scene Mount
  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 540;
    const height = container.clientHeight || 560;

    // 1. Scene & Atmosphere
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0xf8fafc, 0.05);

    // 2. Camera Setup
    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
    camera.position.set(0, 0.35, 4.6);
    camera.lookAt(0, 0, 0);

    // 3. WebGL Renderer with High-Performance Settings
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    // 4. Studio PBR Lighting & Reflections (RoomEnvironment)
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    scene.environment = pmremGenerator.fromScene(new RoomEnvironment(), 0.04).texture;
    pmremGenerator.dispose();

    // Directional Key Light with Soft Shadow Frustum
    const keyLight = new THREE.DirectionalLight(0xfff8ee, 2.2);
    keyLight.position.set(3, 5, 4);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 1024;
    keyLight.shadow.mapSize.height = 1024;
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 12;
    keyLight.shadow.camera.left = -2;
    keyLight.shadow.camera.right = 2;
    keyLight.shadow.camera.top = 2;
    keyLight.shadow.camera.bottom = -2;
    keyLight.shadow.bias = -0.0005;
    keyLight.shadow.normalBias = 0.02;
    scene.add(keyLight);

    // Cool Sky Fill Light
    const fillLight = new THREE.DirectionalLight(0xe0f2fe, 1.2);
    fillLight.position.set(-3, 2, 2);
    scene.add(fillLight);

    // Rim Light & Hemisphere Ambient Fill
    const rimLight = new THREE.DirectionalLight(0xecfdf5, 1.0);
    rimLight.position.set(0, -3, -3);
    scene.add(rimLight);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0xf1f5f9, 0.85);
    scene.add(hemiLight);

    // 5. Procedural Receipt Invoice Canvas Texture
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 1440;
    const ctx = canvas.getContext('2d')!;

    // Clean white paper with subtle ruled lines
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = '#F1F5F9';
    ctx.lineWidth = 1;
    for (let i = 0; i < canvas.height; i += 32) {
      ctx.beginPath();
      ctx.moveTo(0, i);
      ctx.lineTo(canvas.width, i);
      ctx.stroke();
    }

    // Invoice Header
    ctx.fillStyle = '#0F172A';
    ctx.font = 'bold 38px "Plus Jakarta Sans", sans-serif';
    ctx.fillText('THE TAJ WEST END BENGALURU', 80, 110);

    ctx.fillStyle = '#64748B';
    ctx.font = '24px "JetBrains Mono", monospace';
    ctx.fillText('GSTIN: 29AAACT0144Q1ZT · TAX INVOICE', 80, 160);
    ctx.fillText('INV-2026-BLR-8492 · 14 OCT 2026', 80, 200);

    // Dashed divider
    ctx.strokeStyle = '#CBD5E1';
    ctx.setLineDash([8, 8]);
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(80, 240);
    ctx.lineTo(944, 240);
    ctx.stroke();
    ctx.setLineDash([]);

    // Table Header
    ctx.fillStyle = '#334155';
    ctx.font = 'bold 22px "JetBrains Mono", monospace';
    ctx.fillText('DESCRIPTION', 80, 300);
    ctx.fillText('QTY', 640, 300);
    ctx.fillText('TOTAL (INR)', 780, 300);

    // Line items
    const items = [
      { desc: 'Deluxe Corporate Room (1 Night)', qty: '1', amt: '₹7,500.00' },
      { desc: 'Breakfast Executive Buffet', qty: '1', amt: '₹650.00' },
      { desc: 'Airport Sedan Transfer', qty: '1', amt: '₹1,200.00' },
      { desc: 'High-Speed Broadband Internet', qty: '1', amt: 'COMPLIMENTARY' },
    ];

    ctx.font = '24px "JetBrains Mono", monospace';
    let yPos = 360;
    items.forEach((item) => {
      ctx.fillStyle = '#0F172A';
      ctx.fillText(item.desc, 80, yPos);
      ctx.fillStyle = '#64748B';
      ctx.fillText(item.qty, 650, yPos);
      ctx.fillStyle = '#0F172A';
      ctx.fillText(item.amt, 780, yPos);
      yPos += 70;
    });

    // Subtotal & Taxes
    ctx.strokeStyle = '#E2E8F0';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(80, yPos + 20);
    ctx.lineTo(944, yPos + 20);
    ctx.stroke();

    yPos += 70;
    ctx.fillStyle = '#64748B';
    ctx.font = '22px "JetBrains Mono", monospace';
    ctx.fillText('Subtotal (Excl. Taxes):', 80, yPos);
    ctx.fillText('₹9,350.00', 800, yPos);

    yPos += 45;
    ctx.fillText('CGST @ 6.0%:', 80, yPos);
    ctx.fillText('₹561.00', 820, yPos);

    yPos += 45;
    ctx.fillText('SGST @ 6.0%:', 80, yPos);
    ctx.fillText('₹561.00', 820, yPos);

    // Grand Total
    yPos += 70;
    ctx.fillStyle = '#0F172A';
    ctx.font = 'bold 36px "JetBrains Mono", monospace';
    ctx.fillText('GRAND TOTAL:', 80, yPos);
    ctx.fillText('₹10,472.00', 710, yPos);

    // Barcode lines
    yPos += 80;
    ctx.fillStyle = '#1E293B';
    for (let x = 80; x < 944; x += 12) {
      ctx.fillRect(x, yPos, Math.random() * 5 + 2, 70);
    }
    ctx.font = '18px "JetBrains Mono", monospace';
    ctx.fillStyle = '#64748B';
    ctx.fillText('* OCR AUTHENTICATED SERIAL 982-1048-BLR *', 240, yPos + 105);

    // Glowing Compliance Watermark Stamp
    ctx.save();
    ctx.translate(650, 720);
    ctx.rotate(-0.25);
    ctx.strokeStyle = '#15803D';
    ctx.lineWidth = 6;
    ctx.strokeRect(-160, -50, 320, 100);
    ctx.fillStyle = '#15803D';
    ctx.font = 'bold 36px "Plus Jakarta Sans", sans-serif';
    ctx.fillText('AUDIT PASS', -120, 10);
    ctx.font = '20px "JetBrains Mono", monospace';
    ctx.fillText('POL-5.1 COMPLIANT', -115, 36);
    ctx.restore();

    const receiptTexture = new THREE.CanvasTexture(canvas);
    receiptTexture.colorSpace = THREE.SRGBColorSpace;
    receiptTexture.anisotropy = renderer.capabilities.getMaxAnisotropy();

    // 6. Composite 3D Receipt Group Assembly (3–12 parts)
    const receiptGroup = new THREE.Group();

    // Part 1: Main Receipt Paper Mesh (Rounded slab)
    const paperWidth = 1.6;
    const paperHeight = 2.25;
    const paperThickness = 0.02;

    const paperGeometry = new THREE.BoxGeometry(paperWidth, paperHeight, paperThickness, 10, 10, 2);
    const paperMaterial = new THREE.MeshPhysicalMaterial({
      map: receiptTexture,
      roughness: 0.65,
      metalness: 0.05,
      clearcoat: 0.15,
      clearcoatRoughness: 0.4,
      transmission: 0.05,
      thickness: 0.1,
      color: 0xffffff,
    });
    const paperMesh = new THREE.Mesh(paperGeometry, paperMaterial);
    paperMesh.castShadow = true;
    paperMesh.receiveShadow = true;
    receiptGroup.add(paperMesh);

    // Part 2: Top Metallic Clip / Fastener
    const clipGeometry = new THREE.BoxGeometry(0.5, 0.08, 0.06);
    const clipMaterial = new THREE.MeshStandardMaterial({
      color: 0x334155,
      metalness: 0.9,
      roughness: 0.2,
    });
    const clipMesh = new THREE.Mesh(clipGeometry, clipMaterial);
    clipMesh.position.set(0, paperHeight / 2 + 0.02, 0.02);
    clipMesh.castShadow = true;
    receiptGroup.add(clipMesh);

    // Part 3: Animated Verification Rings (Concentric Torus)
    const ringGroup = new THREE.Group();
    const ringGeo1 = new THREE.TorusGeometry(1.35, 0.015, 16, 100);
    const ringMat1 = new THREE.MeshStandardMaterial({
      color: 0x10b981,
      emissive: 0x059669,
      emissiveIntensity: 0.8,
      roughness: 0.3,
      metalness: 0.8,
      transparent: true,
      opacity: 0.75,
    });
    const ring1 = new THREE.Mesh(ringGeo1, ringMat1);
    ring1.rotation.x = Math.PI / 2;
    ringGroup.add(ring1);

    const ringGeo2 = new THREE.TorusGeometry(1.48, 0.01, 16, 100);
    const ringMat2 = new THREE.MeshStandardMaterial({
      color: 0x0ea5e9,
      emissive: 0x0284c7,
      emissiveIntensity: 0.7,
      roughness: 0.2,
      metalness: 0.9,
      transparent: true,
      opacity: 0.6,
    });
    const ring2 = new THREE.Mesh(ringGeo2, ringMat2);
    ring2.rotation.x = Math.PI / 2.3;
    ring2.rotation.y = 0.2;
    ringGroup.add(ring2);

    receiptGroup.add(ringGroup);

    // Part 4: Glowing Compliance Indicator Hexagonal Seal
    const badgeGroup = new THREE.Group();
    const badgeGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.03, 6);
    const badgeMat = new THREE.MeshStandardMaterial({
      color: 0x10b981,
      emissive: 0x047857,
      emissiveIntensity: 0.7,
      metalness: 0.8,
      roughness: 0.2,
    });
    const badgeMesh = new THREE.Mesh(badgeGeo, badgeMat);
    badgeMesh.rotation.x = Math.PI / 2;
    badgeGroup.add(badgeMesh);

    // Inner checkmark emblem on seal
    const checkGeo = new THREE.TorusGeometry(0.08, 0.02, 8, 24, Math.PI * 1.5);
    const checkMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const checkMesh = new THREE.Mesh(checkGeo, checkMat);
    checkMesh.position.set(0, 0, 0.02);
    checkMesh.rotation.z = Math.PI / 4;
    badgeGroup.add(checkMesh);

    badgeGroup.position.set(0.65, -0.85, 0.12);
    receiptGroup.add(badgeGroup);

    // Part 5: Floating OCR Bounding Box Outlines
    const boxGroup = new THREE.Group();
    const createBBox = (w: number, h: number, x: number, y: number) => {
      const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, 0.02));
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: 0x0284c7, transparent: true, opacity: 0.85 })
      );
      line.position.set(x, y, 0.025);
      return line;
    };

    boxGroup.add(
      createBBox(1.2, 0.2, 0, 0.8),
      createBBox(1.3, 0.55, 0, 0.25),
      createBBox(1.2, 0.25, 0, -0.6)
    );
    receiptGroup.add(boxGroup);

    // Part 6: Ambient Audit Particles Field
    const particleCount = 70;
    const particleGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount * 3; i += 3) {
      positions[i] = (Math.random() - 0.5) * 4.2;
      positions[i + 1] = (Math.random() - 0.5) * 4.0;
      positions[i + 2] = (Math.random() - 0.5) * 2.5;
    }
    particleGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const particleMaterial = new THREE.PointsMaterial({
      color: 0x10b981,
      size: 0.035,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particles);

    // Part 7: Ground Contact Shadow Plane
    const shadowCanvas = document.createElement('canvas');
    shadowCanvas.width = 256;
    shadowCanvas.height = 256;
    const sCtx = shadowCanvas.getContext('2d')!;
    const grad = sCtx.createRadialGradient(128, 128, 10, 128, 128, 120);
    grad.addColorStop(0, 'rgba(15, 23, 42, 0.35)');
    grad.addColorStop(0.5, 'rgba(15, 23, 42, 0.12)');
    grad.addColorStop(1, 'rgba(15, 23, 42, 0)');
    sCtx.fillStyle = grad;
    sCtx.fillRect(0, 0, 256, 256);

    const shadowTexture = new THREE.CanvasTexture(shadowCanvas);
    const shadowGeo = new THREE.PlaneGeometry(3.2, 3.2);
    const shadowMat = new THREE.MeshBasicMaterial({
      map: shadowTexture,
      transparent: true,
      depthWrite: false,
    });
    const shadowMesh = new THREE.Mesh(shadowGeo, shadowMat);
    shadowMesh.rotation.x = -Math.PI / 2;
    shadowMesh.position.y = -1.55;
    scene.add(shadowMesh);

    scene.add(receiptGroup);

    // Compile shaders once
    renderer.compile(scene, camera);

    // 7. Interactive Mouse Coordinates with Exponential Damping
    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      stateRef.current.mouseX = x;
      stateRef.current.mouseY = y;
      stateRef.current.targetRotationY = -0.3 + x * 0.45;
      stateRef.current.targetRotationX = 0.1 - y * 0.35;
    };

    window.addEventListener('mousemove', handleMouseMove);

    // 8. 60fps Animation Loop
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      const elapsed = clock.getElapsedTime();

      // Exponential damping on rotation
      receiptGroup.rotation.y = THREE.MathUtils.damp(
        receiptGroup.rotation.y,
        stateRef.current.targetRotationY,
        5.0,
        delta
      );
      receiptGroup.rotation.x = THREE.MathUtils.damp(
        receiptGroup.rotation.x,
        stateRef.current.targetRotationX,
        5.0,
        delta
      );

      // Levitation motion
      const floatY = Math.sin(elapsed * 1.5) * 0.06;
      receiptGroup.position.y = floatY;
      shadowMesh.scale.setScalar(1 - floatY * 0.5);

      // Rings revolution & bobbing
      ringGroup.visible = stateRef.current.showRings;
      if (stateRef.current.showRings) {
        ring1.rotation.z += delta * 0.8;
        ring2.rotation.z -= delta * 0.6;
        const ringBob = Math.sin(elapsed * 2.2) * 0.4;
        ringGroup.position.y = ringBob;
      }

      // OCR bounding box visibility
      boxGroup.visible = stateRef.current.showBoxes;

      // Compliance seal subtle hover
      badgeGroup.rotation.z = Math.sin(elapsed * 2.0) * 0.08;
      badgeGroup.position.z = 0.12 + Math.cos(elapsed * 2.5) * 0.02;

      // Particle slow drift
      particles.rotation.y = elapsed * 0.04;
      particles.rotation.x = Math.sin(elapsed * 0.03) * 0.1;

      // Active verification scan
      if (stateRef.current.isScanning) {
        stateRef.current.scanProgress += delta * 1.5;
        ringGroup.position.y = 1.0 - (stateRef.current.scanProgress % 2.0);
        ringMat1.emissiveIntensity = 1.8;
        ringMat2.emissiveIntensity = 1.6;

        if (stateRef.current.scanProgress >= 2.0) {
          stateRef.current.isScanning = false;
          stateRef.current.scanProgress = 0;
          ringMat1.emissiveIntensity = 0.8;
          ringMat2.emissiveIntensity = 0.7;
          setIsScanning(false);
        }
      }

      renderer.render(scene, camera);
    };

    animate();

    // Responsive ResizeObserver for canvas
    const resizeObserver = new ResizeObserver(() => {
      if (!container) return;
      const w = container.clientWidth || 540;
      const h = container.clientHeight || 560;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    resizeObserver.observe(container);

    return () => {
      cancelAnimationFrame(animId);
      resizeObserver.disconnect();
      window.removeEventListener('mousemove', handleMouseMove);

      paperGeometry.dispose();
      paperMaterial.dispose();
      clipGeometry.dispose();
      clipMaterial.dispose();
      ringGeo1.dispose();
      ringMat1.dispose();
      ringGeo2.dispose();
      ringMat2.dispose();
      badgeGeo.dispose();
      badgeMat.dispose();
      checkGeo.dispose();
      checkMat.dispose();
      particleGeometry.dispose();
      particleMaterial.dispose();
      shadowGeo.dispose();
      shadowMat.dispose();
      receiptTexture.dispose();
      shadowTexture.dispose();
      renderer.dispose();

      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  const triggerScan = () => {
    setIsScanning(true);
    stateRef.current.isScanning = true;
    stateRef.current.scanProgress = 0;
  };

  const resetView = () => {
    stateRef.current.targetRotationX = 0.1;
    stateRef.current.targetRotationY = -0.3;
  };

  return (
    <div className="space-y-16 pb-16 text-slate-900">
      {/* 1. HERO SECTION WITH DIRECT THREE.JS FLOATING 3D RECEIPT */}
      <section className="relative pt-4 pb-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Left Hero Column */}
          <div className="lg:col-span-6 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-slate-100 border border-slate-200 rounded-full text-xs text-slate-700">
              <span className="flex h-2 w-2 rounded-full bg-emerald-500" />
              <span className="font-semibold">Proofline Engine v2026.4</span>
              <span className="text-slate-400">·</span>
              <span className="text-slate-500">Autonomous Evidence Verification</span>
            </div>

            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-900 leading-[1.15]">
              Evidence-First AI Expense Auditing & Policy Compliance
            </h1>

            <p className="text-sm sm:text-base text-slate-600 leading-relaxed max-w-xl">
              Turn messy receipts into accurate, explainable reimbursement decisions.
              Proofline connects multimodal OCR line items to exact policy clauses,
              cumulative allowance caps, and perceptual duplicate detection.
            </p>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <button
                onClick={() => onNavigate('overview')}
                className="flex items-center gap-2 px-5 py-3 text-sm font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-lg transition-colors shadow-xs"
              >
                <span>Launch Audit Console</span>
                <ArrowRight className="h-4 w-4" />
              </button>

              <button
                onClick={() => onNavigate('workbench')}
                className="flex items-center gap-2 px-4 py-3 text-sm font-semibold text-slate-800 bg-white hover:bg-slate-50 border border-slate-200 rounded-lg transition-colors"
              >
                <span>Receipt Workbench</span>
                <ChevronRight className="h-4 w-4 text-slate-400" />
              </button>
            </div>

            {/* Quick Metrics Strip */}
            <div className="grid grid-cols-3 gap-4 pt-6 border-t border-slate-200 max-w-lg">
              <div>
                <div className="font-mono text-xl font-bold text-slate-900">
                  ₹14.25L
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Audited This Cycle
                </div>
              </div>
              <div>
                <div className="font-mono text-xl font-bold text-emerald-700">
                  99.8%
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  OCR Arithmetic Match
                </div>
              </div>
              <div>
                <div className="font-mono text-xl font-bold text-slate-900">
                  3-Valued
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  PASS / UNKNOWN / FAIL
                </div>
              </div>
            </div>
          </div>

          {/* Right Hero Column: Three.js 3D Viewport with Floating Receipt */}
          <div className="lg:col-span-6 bg-gradient-to-b from-slate-100/60 to-white rounded-2xl border border-slate-200/90 shadow-xs p-2 relative overflow-hidden">
            <div className="relative w-full h-[540px] flex items-center justify-center">
              {/* Three.js Canvas Container */}
              <div
                ref={mountRef}
                className="w-full h-full cursor-grab active:cursor-grabbing"
              />

              {/* Floating 3D Control Dock */}
              <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1.5 p-1.5 bg-white/90 border border-slate-200/80 rounded-full shadow-sm text-xs backdrop-blur-xs select-none">
                <button
                  onClick={triggerScan}
                  disabled={isScanning}
                  className="flex items-center gap-1.5 px-3 py-1 bg-slate-900 hover:bg-slate-800 text-white font-medium rounded-full transition-colors disabled:opacity-50 shadow-2xs"
                >
                  <ScanLine className="h-3.5 w-3.5 text-emerald-400" />
                  <span>{isScanning ? 'Scanning Receipt...' : 'Simulate Audit Scan'}</span>
                </button>

                <div className="h-3 w-px bg-slate-200 mx-0.5" />

                <button
                  onClick={() => setShowRings(!showRings)}
                  className={`px-2.5 py-1 rounded-full transition-colors ${
                    showRings ? 'bg-emerald-50 text-emerald-800 font-semibold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Rings: {showRings ? 'On' : 'Off'}
                </button>

                <button
                  onClick={() => setShowBoxes(!showBoxes)}
                  className={`px-2.5 py-1 rounded-full transition-colors ${
                    showBoxes ? 'bg-blue-50 text-blue-800 font-semibold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  OCR Boxes: {showBoxes ? 'On' : 'Off'}
                </button>

                <button
                  onClick={resetView}
                  className="p-1 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-full transition-colors"
                  title="Reset Camera Angles"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
              </div>

              {/* Floating Top Compliance Status Chip */}
              <div className="absolute top-4 right-4 z-10 flex items-center gap-2 bg-white/95 px-3 py-1.5 rounded-full border border-slate-200 shadow-2xs text-[11px] font-medium text-slate-700">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                <span>PBR Audit Verification Engine</span>
                <span className="font-mono text-slate-400">· 99.8%</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. HOW IT WORKS SECTION (3 STEP 3D CARDS) */}
      <section className="space-y-6">
        <div className="text-center max-w-2xl mx-auto space-y-1.5">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Automated Audit Workflow
          </span>
          <h2 className="text-2xl font-bold text-slate-900">
            How Proofline Verifies Every Expense
          </h2>
          <p className="text-xs text-slate-500">
            Three rigorous stages connecting source pixels to policy clause citations and bank disbursements.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Step 1: 3D Scanning Scene */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between">
            <div>
              <div className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden mb-3">
                <Mini3DScene type="scan" />
              </div>

              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-900 text-white">
                  01
                </span>
                <h3 className="text-sm font-bold text-slate-900">
                  Multimodal OCR & Extraction
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                Extracts merchant GSTIN, transaction dates, itemized lines, and integrated taxes with arithmetic reconciliation across receipts and digital invoices.
              </p>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span className="font-mono">Pixel-to-Field Mapping</span>
              <span className="text-emerald-700 font-medium">BBox Verified</span>
            </div>
          </div>

          {/* Step 2: 3D Policy Checking Scene */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between">
            <div>
              <div className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden mb-3">
                <Mini3DScene type="policy" />
              </div>

              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-900 text-white">
                  02
                </span>
                <h3 className="text-sm font-bold text-slate-900">
                  Clause-Grounded Policy Verification
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                Evaluates against city-tier lodging caps, cumulative daily meal limits, and prohibited items, citing exact policy clauses (e.g. Clause 4.2).
              </p>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span className="font-mono">Cumulative Ledger</span>
              <span className="text-blue-700 font-medium">Rule Compiled</span>
            </div>
          </div>

          {/* Step 3: 3D Approval & Payout Scene */}
          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 shadow-2xs hover:shadow-xs transition-shadow flex flex-col justify-between">
            <div>
              <div className="bg-slate-50 rounded-lg border border-slate-100 overflow-hidden mb-3">
                <Mini3DScene type="approve" />
              </div>

              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-900 text-white">
                  03
                </span>
                <h3 className="text-sm font-bold text-slate-900">
                  Immutable Audit & Disbursement
                </h3>
              </div>
              <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                Records state transitions to a cryptographically sealed hash log and routes compliant items to automated payout disbursement via RazorpayX.
              </p>
            </div>

            <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span className="font-mono">SOC-2 Type II Log</span>
              <span className="text-emerald-700 font-medium">Auto-Reimbursed</span>
            </div>
          </div>
        </div>
      </section>

      {/* 3. FOUR CORE CAPABILITIES GRID */}
      <section className="bg-white rounded-2xl border border-slate-200 p-8 shadow-xs space-y-6">
        <div className="max-w-xl">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Governance & Triage
          </span>
          <h2 className="text-xl font-bold text-slate-900 mt-1">
            Built for Enterprise Finance & HR Teams
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Designed to prevent fraudulent bleed while treating employees with transparency and dignity.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div
            onClick={() => onNavigate('workbench')}
            className="cursor-pointer p-4 rounded-xl border border-slate-200 hover:border-slate-400 hover:bg-slate-50/50 transition-all group"
          >
            <div className="flex items-center justify-between text-slate-400 group-hover:text-slate-900">
              <FileSearch className="h-5 w-5" />
              <ChevronRight className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 mt-3">
              Investigation Workbench
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Split-screen viewer with zoom, rotate, and OCR bounding boxes alongside arithmetic verification.
            </p>
          </div>

          <div
            onClick={() => onNavigate('duplicates')}
            className="cursor-pointer p-4 rounded-xl border border-slate-200 hover:border-slate-400 hover:bg-slate-50/50 transition-all group"
          >
            <div className="flex items-center justify-between text-slate-400 group-hover:text-slate-900">
              <Scale className="h-5 w-5" />
              <ChevronRight className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 mt-3">
              Duplicate Review
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Perceptual image hash matching and side-by-side comparison without premature fraud accusations.
            </p>
          </div>

          <div
            onClick={() => onNavigate('policy-studio')}
            className="cursor-pointer p-4 rounded-xl border border-slate-200 hover:border-slate-400 hover:bg-slate-50/50 transition-all group"
          >
            <div className="flex items-center justify-between text-slate-400 group-hover:text-slate-900">
              <Layers className="h-5 w-5" />
              <ChevronRight className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 mt-3">
              Policy Studio
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Drag-and-drop corporate PDF uploader compiling natural-language text into mathematical rules.
            </p>
          </div>

          <div
            onClick={() => onNavigate('audit-trail')}
            className="cursor-pointer p-4 rounded-xl border border-slate-200 hover:border-slate-400 hover:bg-slate-50/50 transition-all group"
          >
            <div className="flex items-center justify-between text-slate-400 group-hover:text-slate-900">
              <Lock className="h-5 w-5" />
              <ChevronRight className="h-4 w-4" />
            </div>
            <h3 className="text-sm font-bold text-slate-900 mt-3">
              Audit Trail & Exports
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Immutable state changes and reviewer reasoning with CSV and PDF evidence pack export.
            </p>
          </div>
        </div>
      </section>

      {/* 4. BOTTOM ACTION CALLOUT */}
      <section className="bg-slate-900 text-white rounded-2xl p-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold">
            <CheckCircle2 className="h-4 w-4" />
            <span>Ready for Review</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight">
            Explore the Live Proofline Enterprise Console
          </h2>
          <p className="text-xs text-slate-400 max-w-lg">
            Inspect pending receipts, test duplicate image hash matching, and evaluate cumulative allowance caps.
          </p>
        </div>

        <button
          onClick={() => onNavigate('overview')}
          className="flex items-center gap-2 px-5 py-3 text-xs font-semibold text-slate-900 bg-white hover:bg-slate-100 rounded-lg transition-colors whitespace-nowrap shadow-xs"
        >
          <span>Open Overview Dashboard</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </section>
    </div>
  );
};
