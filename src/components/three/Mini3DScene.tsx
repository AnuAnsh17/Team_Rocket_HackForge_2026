import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

interface Mini3DSceneProps {
  type: 'scan' | 'policy' | 'approve';
}

export const Mini3DScene: React.FC<Mini3DSceneProps> = ({ type }) => {
  const mountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 240;
    const height = container.clientHeight || 180;

    // Scene
    const scene = new THREE.Scene();

    // Camera
    const camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 50);
    camera.position.set(0, 0, 3.8);

    // Renderer
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    // Studio Lights
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.8);
    keyLight.position.set(3, 4, 3);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xdbeafe, 1.0);
    fillLight.position.set(-3, -1, 2);
    scene.add(fillLight);

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0xf1f5f9, 0.7);
    scene.add(hemiLight);

    // Objects Group
    const group = new THREE.Group();

    let scanLine: THREE.Mesh | null = null;
    let ring1: THREE.Mesh | null = null;
    let ring2: THREE.Mesh | null = null;
    let shieldMesh: THREE.Mesh | null = null;
    let sealGroup: THREE.Group | null = null;

    if (type === 'scan') {
      // Step 1: Receipt Scanning & OCR Extraction
      // Paper base
      const paperGeo = new THREE.BoxGeometry(1.2, 1.6, 0.03);
      const paperMat = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        roughness: 0.5,
        metalness: 0.1,
      });
      const paper = new THREE.Mesh(paperGeo, paperMat);
      group.add(paper);

      // OCR simulated text lines
      for (let y = 0.5; y >= -0.5; y -= 0.22) {
        const lineGeo = new THREE.BoxGeometry(Math.random() * 0.4 + 0.6, 0.04, 0.035);
        const lineMat = new THREE.MeshBasicMaterial({ color: 0x94a3b8 });
        const lineMesh = new THREE.Mesh(lineGeo, lineMat);
        lineMesh.position.set(-0.1, y, 0.01);
        group.add(lineMesh);
      }

      // Moving Laser Scanner Line
      const scanGeo = new THREE.BoxGeometry(1.3, 0.03, 0.04);
      const scanMat = new THREE.MeshStandardMaterial({
        color: 0x0284c7,
        emissive: 0x38bdf8,
        emissiveIntensity: 1.5,
      });
      scanLine = new THREE.Mesh(scanGeo, scanMat);
      scanLine.position.z = 0.04;
      group.add(scanLine);

      // Bounding box brackets
      const bboxGeo = new THREE.EdgesGeometry(new THREE.BoxGeometry(0.8, 0.25, 0.04));
      const bboxLine = new THREE.LineSegments(
        bboxGeo,
        new THREE.LineBasicMaterial({ color: 0x10b981 })
      );
      bboxLine.position.set(0, 0.1, 0.03);
      group.add(bboxLine);
    } else if (type === 'policy') {
      // Step 2: Policy Checking & Cumulative Verification
      // Shield Geometry
      const shieldGeo = new THREE.CylinderGeometry(0.6, 0.3, 1.2, 6);
      const shieldMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        roughness: 0.2,
        metalness: 0.8,
      });
      shieldMesh = new THREE.Mesh(shieldGeo, shieldMat);
      shieldMesh.rotation.z = Math.PI;
      group.add(shieldMesh);

      // Concentric Policy Check Rings
      const ringGeoA = new THREE.TorusGeometry(0.95, 0.02, 12, 48);
      const ringMatA = new THREE.MeshStandardMaterial({
        color: 0x10b981,
        emissive: 0x059669,
        emissiveIntensity: 1.0,
      });
      ring1 = new THREE.Mesh(ringGeoA, ringMatA);
      group.add(ring1);

      const ringGeoB = new THREE.TorusGeometry(1.15, 0.015, 12, 48);
      const ringMatB = new THREE.MeshStandardMaterial({
        color: 0x0ea5e9,
        emissive: 0x0284c7,
        emissiveIntensity: 0.8,
      });
      ring2 = new THREE.Mesh(ringGeoB, ringMatB);
      group.add(ring2);
    } else {
      // Step 3: Automated Payout & Immutable Approval
      sealGroup = new THREE.Group();

      // Hexagonal Seal Base
      const sealGeo = new THREE.CylinderGeometry(0.75, 0.75, 0.1, 6);
      const sealMat = new THREE.MeshStandardMaterial({
        color: 0x15803d,
        emissive: 0x166534,
        emissiveIntensity: 0.5,
        roughness: 0.2,
        metalness: 0.7,
      });
      const sealMesh = new THREE.Mesh(sealGeo, sealMat);
      sealMesh.rotation.x = Math.PI / 2;
      sealGroup.add(sealMesh);

      // Checkmark Torus
      const checkGeo = new THREE.TorusGeometry(0.35, 0.06, 12, 32, Math.PI * 1.4);
      const checkMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const checkMesh = new THREE.Mesh(checkGeo, checkMat);
      checkMesh.position.set(0, 0, 0.08);
      checkMesh.rotation.z = Math.PI / 4;
      sealGroup.add(checkMesh);

      // Orbiting particles
      const orbitGeo = new THREE.TorusGeometry(1.05, 0.015, 8, 48);
      const orbitMat = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        emissive: 0x0284c7,
        emissiveIntensity: 0.8,
      });
      ring1 = new THREE.Mesh(orbitGeo, orbitMat);
      ring1.rotation.x = 0.5;
      group.add(ring1);

      group.add(sealGroup);
    }

    scene.add(group);

    // Hover state
    let isHovered = false;
    let hoverScale = 1.0;
    const onEnter = () => { isHovered = true; };
    const onLeave = () => { isHovered = false; };
    container.addEventListener('mouseenter', onEnter);
    container.addEventListener('mouseleave', onLeave);

    // Animation Loop
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      const elapsed = clock.getElapsedTime();
      const speedMultiplier = isHovered ? 2.2 : 1.0;

      // Smooth hover scale
      hoverScale = THREE.MathUtils.damp(hoverScale, isHovered ? 1.08 : 1.0, 5.0, delta);
      group.scale.setScalar(hoverScale);

      // Gentle group rotation
      group.rotation.y = Math.sin(elapsed * 1.2 * speedMultiplier) * 0.3;
      group.rotation.x = Math.cos(elapsed * 0.9 * speedMultiplier) * 0.12;

      if (type === 'scan' && scanLine) {
        scanLine.position.y = Math.sin(elapsed * 2.5 * speedMultiplier) * 0.7;
      }

      if (type === 'policy') {
        if (ring1) ring1.rotation.z += delta * 1.2 * speedMultiplier;
        if (ring2) ring2.rotation.x -= delta * 0.9 * speedMultiplier;
        if (shieldMesh) shieldMesh.position.y = Math.sin(elapsed * 2) * 0.04;
      }

      if (type === 'approve') {
        if (ring1) ring1.rotation.z += delta * 1.5 * speedMultiplier;
        if (sealGroup) sealGroup.rotation.z = Math.sin(elapsed * 1.5 * speedMultiplier) * 0.15;
      }

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animId);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [type]);

  return (
    <div
      ref={mountRef}
      className="w-full h-44 flex items-center justify-center select-none"
    />
  );
};
