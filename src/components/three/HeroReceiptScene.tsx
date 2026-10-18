import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { Sparkles, CheckCircle2, RotateCcw, ScanLine } from 'lucide-react';

interface HeroReceiptSceneProps {
  onScanComplete?: () => void;
}

export const HeroReceiptScene: React.FC<HeroReceiptSceneProps> = ({ onScanComplete }) => {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationPassed, setVerificationPassed] = useState(true);
  const [showRings, setShowRings] = useState(true);
  const [showBoxes, setShowBoxes] = useState(true);

  // References to communicate with Three.js render loop without remounting
  const stateRef = useRef({
    mouseX: 0,
    mouseY: 0,
    targetRotationX: 0.1,
    targetRotationY: -0.3,
    scrollY: 0,
    isScanning: false,
    scanProgress: 0,
    showRings: true,
    showBoxes: true,
    isHovered: false,
    hoverFactor: 0,
  });

  useEffect(() => {
    stateRef.current.showRings = showRings;
    stateRef.current.showBoxes = showBoxes;
  }, [showRings, showBoxes]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Dimensions
    const width = container.clientWidth || 540;
    const height = container.clientHeight || 560;

    // 1. Scene setup
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0xf8fafc, 0.05);

    // 2. Camera setup
    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
    camera.position.set(0, 0.4, 4.6);
    camera.lookAt(0, 0, 0);

    // 3. Renderer setup
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

    // 4. Studio PBR Lighting & Environment
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    scene.environment = pmremGenerator.fromScene(new RoomEnvironment(), 0.04).texture;
    pmremGenerator.dispose();

    // Key Light (Warm soft studio directional)
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

    // Fill Light (Cool sky blue)
    const fillLight = new THREE.DirectionalLight(0xe0f2fe, 1.2);
    fillLight.position.set(-3, 2, 2);
    scene.add(fillLight);

    // Subtle Rim Light
    const rimLight = new THREE.DirectionalLight(0xecfdf5, 1.0);
    rimLight.position.set(0, -3, -3);
    scene.add(rimLight);

    // Hemisphere Light
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0xf1f5f9, 0.8);
    scene.add(hemiLight);

    // 5. Procedural Texture for Receipt Invoice
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 1440;
    const ctx = canvas.getContext('2d')!;

    // Background paper texture
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Subtle paper grain/lines
    ctx.strokeStyle = '#F1F5F9';
    ctx.lineWidth = 1;
    for (let i = 0; i < canvas.height; i += 32) {
      ctx.beginPath();
      ctx.moveTo(0, i);
      ctx.lineTo(canvas.width, i);
      ctx.stroke();
    }

    // Header band
    ctx.fillStyle = '#0F172A';
    ctx.font = 'bold 38px "Plus Jakarta Sans", sans-serif';
    ctx.fillText('THE TAJ WEST END BENGALURU', 80, 110);

    ctx.fillStyle = '#64748B';
    ctx.font = '24px "JetBrains Mono", monospace';
    ctx.fillText('GSTIN: 29AAACT0144Q1ZT · TAX INVOICE', 80, 160);
    ctx.fillText('INV-2026-BLR-8492 · 14 OCT 2026', 80, 200);

    // Hairline divider
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

    // Divider
    ctx.strokeStyle = '#E2E8F0';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(80, yPos + 20);
    ctx.lineTo(944, yPos + 20);
    ctx.stroke();

    // Tax Subtotals
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

    // Barcode lines at bottom
    yPos += 80;
    ctx.fillStyle = '#1E293B';
    for (let x = 80; x < 944; x += Math.random() * 14 + 6) {
      ctx.fillRect(x, yPos, Math.random() * 4 + 2, 70);
    }
    ctx.font = '18px "JetBrains Mono", monospace';
    ctx.fillStyle = '#64748B';
    ctx.fillText('* OCR AUTHENTICATED SERIAL 982-1048-BLR *', 240, yPos + 105);

    // Verified Watermark Stamp
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

    // 6. Composite 3D Receipt Group (3-12 parts)
    const receiptGroup = new THREE.Group();

    // Part 1: Main Receipt Paper (Rounded Extrude / Bevel Slab)
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

    // Part 3: Floating Holographic Verification Rings (Torus)
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

    // Part 4: Floating Verification Badge / Hexagonal Seal
    const badgeGroup = new THREE.Group();
    const badgeGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.03, 6);
    const badgeMat = new THREE.MeshStandardMaterial({
      color: 0x10b981,
      emissive: 0x047857,
      emissiveIntensity: 0.6,
      metalness: 0.8,
      roughness: 0.2,
    });
    const badgeMesh = new THREE.Mesh(badgeGeo, badgeMat);
    badgeMesh.rotation.x = Math.PI / 2;
    badgeGroup.add(badgeMesh);

    // Inner checkmark emblem
    const checkGeo = new THREE.TorusGeometry(0.08, 0.02, 8, 24, Math.PI * 1.5);
    const checkMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const checkMesh = new THREE.Mesh(checkGeo, checkMat);
    checkMesh.position.set(0, 0, 0.02);
    checkMesh.rotation.z = Math.PI / 4;
    badgeGroup.add(checkMesh);

    badgeGroup.position.set(0.65, -0.85, 0.12);
    receiptGroup.add(badgeGroup);

    // Part 5: Floating Bounding Box Outlines over OCR detected areas
    const boxGroup = new THREE.Group();

    const createBoundingWireframe = (w: number, h: number, x: number, y: number) => {
      const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, 0.02));
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: 0x0284c7, transparent: true, opacity: 0.85 })
      );
      line.position.set(x, y, 0.025);
      return line;
    };

    const bbox1 = createBoundingWireframe(1.2, 0.2, 0, 0.8); // Header
    const bbox2 = createBoundingWireframe(1.3, 0.55, 0, 0.25); // Line Items
    const bbox3 = createBoundingWireframe(1.2, 0.25, 0, -0.6); // Total
    boxGroup.add(bbox1, bbox2, bbox3);
    receiptGroup.add(boxGroup);

    // Part 6: Subtle Ambient Audit Particles
    const particleCount = 70;
    const particleGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const scales = new Float32Array(particleCount);

    for (let i = 0; i < particleCount * 3; i += 3) {
      positions[i] = (Math.random() - 0.5) * 4.2;
      positions[i + 1] = (Math.random() - 0.5) * 4.0;
      positions[i + 2] = (Math.random() - 0.5) * 2.5;
      scales[i / 3] = Math.random() * 0.04 + 0.015;
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

    // Part 7: Ground Contact Shadow (Soft radial blur)
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

    // Pre-warm shaders
    renderer.compile(scene, camera);

    // 7. Mouse, Hover & Scroll interaction handlers
    const handleMouseEnter = () => {
      stateRef.current.isHovered = true;
    };

    const handleMouseLeave = () => {
      stateRef.current.isHovered = false;
      stateRef.current.targetRotationX = 0.1;
      stateRef.current.targetRotationY = -0.3;
      stateRef.current.mouseX = 0;
      stateRef.current.mouseY = 0;
    };

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      stateRef.current.mouseX = x;
      stateRef.current.mouseY = y;
      stateRef.current.targetRotationY = -0.3 + x * 0.55;
      stateRef.current.targetRotationX = 0.1 - y * 0.4;
    };

    const handleScroll = () => {
      stateRef.current.scrollY = window.scrollY;
    };

    container.addEventListener('mouseenter', handleMouseEnter);
    container.addEventListener('mouseleave', handleMouseLeave);
    container.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('scroll', handleScroll, { passive: true });

    // 8. Animation Loop
    let animationFrameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      const elapsed = clock.getElapsedTime();

      // Exponential damping for smooth hover interpolation (0 to 1)
      const targetHover = stateRef.current.isHovered ? 1.0 : 0.0;
      stateRef.current.hoverFactor = THREE.MathUtils.damp(
        stateRef.current.hoverFactor,
        targetHover,
        5.5,
        delta
      );
      const hf = stateRef.current.hoverFactor;

      // Exponential Damping for smooth rotation & tilt
      receiptGroup.rotation.y = THREE.MathUtils.damp(
        receiptGroup.rotation.y,
        stateRef.current.targetRotationY,
        5.5,
        delta
      );
      receiptGroup.rotation.x = THREE.MathUtils.damp(
        receiptGroup.rotation.x,
        stateRef.current.targetRotationX,
        5.5,
        delta
      );

      // Interactive 3D hover elevation and scale expansion
      const currentScale = 1.0 + hf * 0.07;
      receiptGroup.scale.set(currentScale, currentScale, currentScale);

      // Gentle floating levitation motion + hover elevation
      const floatY = Math.sin(elapsed * (1.5 + hf * 0.8)) * 0.06;
      receiptGroup.position.y = floatY + hf * 0.14;
      receiptGroup.position.z = hf * 0.32;

      // Dynamic ground contact shadow response
      const shadowScale = (1 - floatY * 0.5) * (1 + hf * 0.3);
      shadowMesh.scale.setScalar(shadowScale);
      shadowMat.opacity = 0.85 - hf * 0.25;

      // Rings revolution, expansion & bobbing
      ringGroup.visible = stateRef.current.showRings;
      if (stateRef.current.showRings) {
        const ringScale = 1.0 + hf * 0.16;
        ringGroup.scale.set(ringScale, ringScale, ringScale);

        const ringSpeed = 1.0 + hf * 2.2;
        ring1.rotation.z += delta * 0.8 * ringSpeed;
        ring2.rotation.z -= delta * 0.6 * ringSpeed;
        const ringBob = Math.sin(elapsed * 2.2) * (0.35 + hf * 0.15);
        ringGroup.position.y = ringBob;

        if (!stateRef.current.isScanning) {
          ringMat1.emissiveIntensity = 0.8 + hf * 0.9;
          ringMat2.emissiveIntensity = 0.7 + hf * 0.8;
        }
      }

      // Bounding box visibility & pulse
      boxGroup.visible = stateRef.current.showBoxes;
      if (stateRef.current.showBoxes) {
        const boxPulse = Math.sin(elapsed * 4.0) * 0.15 + 0.85;
        boxGroup.children.forEach((child) => {
          if ((child as THREE.LineSegments).material) {
            const mat = (child as THREE.LineSegments).material as THREE.LineBasicMaterial;
            mat.opacity = (0.7 + hf * 0.3) * boxPulse;
          }
        });
      }

      // Verification Badge subtle hover & spin
      badgeGroup.rotation.z = Math.sin(elapsed * (2.0 + hf * 1.5)) * 0.1;
      badgeGroup.position.z = 0.12 + hf * 0.06 + Math.cos(elapsed * 2.5) * 0.02;
      badgeMat.emissiveIntensity = 0.7 + hf * 0.7;

      // Ambient particle slow rotation & drift
      const particleSpeed = 1.0 + hf * 1.8;
      particles.rotation.y = elapsed * 0.04 * particleSpeed;
      particles.rotation.x = Math.sin(elapsed * 0.03 * particleSpeed) * 0.12;
      particleMaterial.size = 0.035 + hf * 0.015;
      particleMaterial.opacity = 0.65 + hf * 0.25;

      // Active verification scan simulation
      if (stateRef.current.isScanning) {
        stateRef.current.scanProgress += delta * 1.5;
        ringGroup.position.y = 1.0 - (stateRef.current.scanProgress % 2.0);
        ringMat1.emissiveIntensity = 1.8;
        ringMat2.emissiveIntensity = 1.6;

        if (stateRef.current.scanProgress >= 2.0) {
          stateRef.current.isScanning = false;
          stateRef.current.scanProgress = 0;
          ringMat1.emissiveIntensity = 0.8 + hf * 0.9;
          ringMat2.emissiveIntensity = 0.7 + hf * 0.8;
          setIsVerifying(false);
          if (onScanComplete) onScanComplete();
        }
      }

      renderer.render(scene, camera);
    };

    animate();

    // Resize handler
    const handleResize = () => {
      if (!container) return;
      const newWidth = container.clientWidth;
      const newHeight = container.clientHeight;
      camera.aspect = newWidth / newHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(newWidth, newHeight);
    };
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      container.removeEventListener('mouseenter', handleMouseEnter);
      container.removeEventListener('mouseleave', handleMouseLeave);
      container.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);

      // Dispose Three.js objects
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
    setIsVerifying(true);
    stateRef.current.isScanning = true;
    stateRef.current.scanProgress = 0;
  };

  const resetView = () => {
    stateRef.current.targetRotationX = 0.1;
    stateRef.current.targetRotationY = -0.3;
  };

  return (
    <div className="relative w-full h-[540px] flex items-center justify-center">
      {/* Three.js Canvas Container */}
      <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Floating 3D Control Strip (Collapsible & Non-obstructive) */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1.5 p-1.5 bg-white/90 border border-slate-200/80 rounded-full shadow-sm text-xs backdrop-blur-xs select-none">
        <button
          onClick={triggerScan}
          disabled={isVerifying}
          className="flex items-center gap-1.5 px-3 py-1 bg-slate-900 hover:bg-slate-800 text-white font-medium rounded-full transition-colors disabled:opacity-50 shadow-2xs"
        >
          <ScanLine className="h-3.5 w-3.5 text-emerald-400" />
          <span>{isVerifying ? 'Scanning Receipt...' : 'Simulate Audit Scan'}</span>
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
        <span>PBR Pervasive Audit Verified</span>
        <span className="font-mono text-slate-400">· 99.8%</span>
      </div>
    </div>
  );
};
