"""아동부 PPT 애니메이션 XML 주입 — 19개 실작업 PPT 분석 기반 (장년부와 완전 독립)

핵심 패턴:
- Appear + Color Pulse HSL (presetID=1 + 21): 빨간 마스크 리빌 ⭐ 최다
- Fade In (presetID=10): 텍스트/이미지 등장
- Appear + Object Color + Scale (presetID=1 + 26): 거대 ? 효과
- Fade Out (presetID=10, exit): 마스크 제거
"""

from lxml import etree

NS_P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'

# ============================================================
# 1. Fade 입장 (presetID=10, 500ms) — 텍스트/이미지 등장
# ============================================================
ANIM_FADE_IN_XML = '''<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
                <p:par>
                  <p:cTn id="3" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="4" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
                            <p:par>
                              <p:cTn id="5" presetID="10" presetClass="entr" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="clickEffect">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:set>
                                    <p:cBhvr>
                                      <p:cTn id="6" dur="1" fill="hold">
                                        <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                      </p:cTn>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:to><p:strVal val="visible"/></p:to>
                                  </p:set>
                                  <p:animEffect transition="in" filter="fade">
                                    <p:cBhvr>
                                      <p:cTn id="7" dur="500"/>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                    </p:cBhvr>
                                  </p:animEffect>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
            <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
  <p:bldLst>
    <p:bldP spid="{shape_id}" grpId="0"/>
  </p:bldLst>
</p:timing>'''


# ============================================================
# 2. Appear + Color Pulse HSL (presetID=1 + 21) — 빨간 마스크 리빌 ⭐
# 클릭 시 빨간 도형이 나타나면서 색상 순환 깜빡임
# ============================================================
ANIM_APPEAR_COLORPULSE_XML = '''<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
                <p:par>
                  <p:cTn id="3" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="4" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
                            <p:par>
                              <p:cTn id="5" presetID="1" presetClass="entr" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="clickEffect">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:set>
                                    <p:cBhvr>
                                      <p:cTn id="6" dur="1" fill="hold">
                                        <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                      </p:cTn>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:to><p:strVal val="visible"/></p:to>
                                  </p:set>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                            <p:par>
                              <p:cTn id="7" presetID="21" presetClass="emph" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="withEffect"
                                     repeatCount="indefinite">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:animClr clrSpc="hsl" dir="cw">
                                    <p:cBhvr>
                                      <p:cTn id="8" dur="500" fill="hold"/>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>fillcolor</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:by>
                                      <p:hsl h="0" s="0" l="0"/>
                                    </p:by>
                                  </p:animClr>
                                  <p:animClr clrSpc="hsl" dir="cw">
                                    <p:cBhvr>
                                      <p:cTn id="9" dur="500" fill="hold"/>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>fill.type</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:by>
                                      <p:hsl h="0" s="0" l="0"/>
                                    </p:by>
                                  </p:animClr>
                                  <p:animClr clrSpc="hsl" dir="cw">
                                    <p:cBhvr>
                                      <p:cTn id="10" dur="500" fill="hold"/>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>stroke.color</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:by>
                                      <p:hsl h="0" s="0" l="0"/>
                                    </p:by>
                                  </p:animClr>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
            <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
  <p:bldLst>
    <p:bldP spid="{shape_id}" grpId="0"/>
  </p:bldLst>
</p:timing>'''


# ============================================================
# 3. 거대 ? 효과 (Appear + Object Color + Scale)
# 2개 도형: 빨간 타원 + 거대 ? 텍스트
# ============================================================
ANIM_QUESTION_XML = '''<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
                <!-- 클릭 1: 빨간 타원 Appear + Color Pulse -->
                <p:par>
                  <p:cTn id="3" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="4" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
                            <p:par>
                              <p:cTn id="5" presetID="1" presetClass="entr" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="clickEffect">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:set>
                                    <p:cBhvr>
                                      <p:cTn id="6" dur="1" fill="hold">
                                        <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                      </p:cTn>
                                      <p:tgtEl><p:spTgt spid="{oval_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:to><p:strVal val="visible"/></p:to>
                                  </p:set>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                            <p:par>
                              <p:cTn id="7" presetID="21" presetClass="emph" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="withEffect"
                                     repeatCount="indefinite">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:animClr clrSpc="hsl" dir="cw">
                                    <p:cBhvr>
                                      <p:cTn id="8" dur="500" fill="hold"/>
                                      <p:tgtEl><p:spTgt spid="{oval_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>fillcolor</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:by><p:hsl h="0" s="0" l="0"/></p:by>
                                  </p:animClr>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>
                <!-- 클릭 2: 거대 ? Fade In + Object Color 강조 -->
                <p:par>
                  <p:cTn id="9" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="10" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
                            <p:par>
                              <p:cTn id="11" presetID="10" presetClass="entr" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="clickEffect">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:set>
                                    <p:cBhvr>
                                      <p:cTn id="12" dur="1" fill="hold">
                                        <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                      </p:cTn>
                                      <p:tgtEl><p:spTgt spid="{text_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:to><p:strVal val="visible"/></p:to>
                                  </p:set>
                                  <p:animEffect transition="in" filter="fade">
                                    <p:cBhvr>
                                      <p:cTn id="13" dur="500"/>
                                      <p:tgtEl><p:spTgt spid="{text_id}"/></p:tgtEl>
                                    </p:cBhvr>
                                  </p:animEffect>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                            <p:par>
                              <p:cTn id="14" presetID="26" presetClass="emph" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="withEffect"
                                     repeatCount="indefinite">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:animScale>
                                    <p:cBhvr>
                                      <p:cTn id="15" dur="500" autoRev="1" fill="hold"/>
                                      <p:tgtEl><p:spTgt spid="{text_id}"/></p:tgtEl>
                                    </p:cBhvr>
                                    <p:by x="105000" y="105000"/>
                                  </p:animScale>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
            <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
  <p:bldLst>
    <p:bldP spid="{oval_id}" grpId="0"/>
    <p:bldP spid="{text_id}" grpId="0"/>
  </p:bldLst>
</p:timing>'''


# ============================================================
# 4. 멀티 클릭 Appear + Color Pulse (빨간 마스크 N개 순차 등장)
# {click_blocks} 에 N개의 클릭 블록을 삽입
# {build_entries} 에 N개의 bldP를 삽입
# ============================================================
ANIM_MULTI_MASK_TEMPLATE = '''<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
{click_blocks}
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
            <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
  <p:bldLst>
{build_entries}
  </p:bldLst>
</p:timing>'''

# 개별 클릭 블록 (마스크 하나당)
CLICK_BLOCK_APPEAR_COLORPULSE = '''                <p:par>
                  <p:cTn id="{base_id}" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="{id2}" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
                            <p:par>
                              <p:cTn id="{id3}" presetID="1" presetClass="entr" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="clickEffect">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:set>
                                    <p:cBhvr>
                                      <p:cTn id="{id4}" dur="1" fill="hold">
                                        <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                      </p:cTn>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:to><p:strVal val="visible"/></p:to>
                                  </p:set>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                            <p:par>
                              <p:cTn id="{id5}" presetID="21" presetClass="emph" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="withEffect"
                                     repeatCount="indefinite">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:animClr clrSpc="hsl" dir="cw">
                                    <p:cBhvr>
                                      <p:cTn id="{id6}" dur="500" fill="hold"/>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>fillcolor</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:by><p:hsl h="0" s="0" l="0"/></p:by>
                                  </p:animClr>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>'''


def _inject_timing_xml(slide, xml_str):
    """기존 timing 제거 후 새 XML 주입 (현재 비활성화)"""
    # 비활성화: python-pptx로 수동 삽입한 timing XML이 PowerPoint "복구" 메시지를 유발.
    # 본문은 미리보기 이미지(text_PP.png) 풀스크린이라 애니메이션 불필요 → 정적 슬라이드.
    return
    slide_elem = slide._element
    for old in slide_elem.findall(f'{NS_P}timing'):
        slide_elem.remove(old)
    timing_elem = etree.fromstring(xml_str.encode('utf-8'))
    slide_elem.append(timing_elem)


def inject_fade_in(slide, shape_id):
    """Fade In 애니메이션 (500ms)"""
    xml = ANIM_FADE_IN_XML.format(shape_id=shape_id)
    _inject_timing_xml(slide, xml)


def inject_appear_colorpulse(slide, shape_id):
    """Appear + Color Pulse 애니메이션 (빨간 마스크 1개)"""
    xml = ANIM_APPEAR_COLORPULSE_XML.format(shape_id=shape_id)
    _inject_timing_xml(slide, xml)


def inject_question_animation(slide, oval_id, text_id):
    """거대 ? 효과 (빨간 타원 + ? 텍스트)"""
    xml = ANIM_QUESTION_XML.format(oval_id=oval_id, text_id=text_id)
    _inject_timing_xml(slide, xml)


def inject_multi_mask_animation(slide, shape_ids):
    """복수 빨간 마스크 순차 등장 (클릭마다 하나씩)"""
    if not shape_ids:
        return

    click_blocks = []
    build_entries = []
    ctn_id = 3  # id counter (1,2는 root/mainSeq)

    for sid in shape_ids:
        block = CLICK_BLOCK_APPEAR_COLORPULSE.format(
            base_id=ctn_id, id2=ctn_id+1, id3=ctn_id+2,
            id4=ctn_id+3, id5=ctn_id+4, id6=ctn_id+5,
            shape_id=sid
        )
        click_blocks.append(block)
        build_entries.append(f'    <p:bldP spid="{sid}" grpId="0"/>')
        ctn_id += 6

    xml = ANIM_MULTI_MASK_TEMPLATE.format(
        click_blocks='\n'.join(click_blocks),
        build_entries='\n'.join(build_entries)
    )
    _inject_timing_xml(slide, xml)


# ============================================================
# 5. 동시 Fade In — 여러 도형이 첫 클릭에 함께 나타남 (표지용)
# ============================================================
FADE_BLOCK = '''                            <p:par>
                              <p:cTn id="{ctn_id}" presetID="10" presetClass="entr" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="{node_type}">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:set>
                                    <p:cBhvr>
                                      <p:cTn id="{ctn_id2}" dur="1" fill="hold">
                                        <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                      </p:cTn>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:to><p:strVal val="visible"/></p:to>
                                  </p:set>
                                  <p:animEffect transition="in" filter="fade">
                                    <p:cBhvr>
                                      <p:cTn id="{ctn_id3}" dur="500"/>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                    </p:cBhvr>
                                  </p:animEffect>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>'''

ANIM_MULTI_FADE_TEMPLATE = '''<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
                <p:par>
                  <p:cTn id="3" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="4" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
{fade_blocks}
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
            <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
  <p:bldLst>
{build_entries}
  </p:bldLst>
</p:timing>'''


# ============================================================
# 6. 순차 Fade In — 클릭마다 하나씩 Fade In (원어, 텍스트용)
# ============================================================
CLICK_FADE_BLOCK = '''                <p:par>
                  <p:cTn id="{base_id}" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="{id2}" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
                            <p:par>
                              <p:cTn id="{id3}" presetID="10" presetClass="entr" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="clickEffect">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:set>
                                    <p:cBhvr>
                                      <p:cTn id="{id4}" dur="1" fill="hold">
                                        <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                      </p:cTn>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                      <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                                    </p:cBhvr>
                                    <p:to><p:strVal val="visible"/></p:to>
                                  </p:set>
                                  <p:animEffect transition="in" filter="fade">
                                    <p:cBhvr>
                                      <p:cTn id="{id5}" dur="500"/>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                    </p:cBhvr>
                                  </p:animEffect>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>'''

ANIM_CLICK_FADE_TEMPLATE = '''<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
{click_blocks}
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
            <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
  <p:bldLst>
{build_entries}
  </p:bldLst>
</p:timing>'''


def inject_multi_fade_in(slide, shape_ids):
    """여러 도형이 첫 클릭에 동시 Fade In (표지/이미지 슬라이드용)"""
    if not shape_ids:
        return

    fade_blocks = []
    build_entries = []
    ctn_id = 5  # 1=root, 2=mainSeq, 3=par, 4=par

    for i, sid in enumerate(shape_ids):
        node_type = "clickEffect" if i == 0 else "withEffect"
        block = FADE_BLOCK.format(
            ctn_id=ctn_id, ctn_id2=ctn_id + 1, ctn_id3=ctn_id + 2,
            shape_id=sid, node_type=node_type
        )
        fade_blocks.append(block)
        build_entries.append(f'    <p:bldP spid="{sid}" grpId="0"/>')
        ctn_id += 3

    xml = ANIM_MULTI_FADE_TEMPLATE.format(
        fade_blocks='\n'.join(fade_blocks),
        build_entries='\n'.join(build_entries)
    )
    _inject_timing_xml(slide, xml)


def inject_click_fade_in(slide, shape_ids):
    """도형들이 클릭마다 순차 Fade In (원어/텍스트 슬라이드용)"""
    if not shape_ids:
        return

    click_blocks = []
    build_entries = []
    ctn_id = 3

    for sid in shape_ids:
        block = CLICK_FADE_BLOCK.format(
            base_id=ctn_id, id2=ctn_id + 1, id3=ctn_id + 2,
            id4=ctn_id + 3, id5=ctn_id + 4,
            shape_id=sid
        )
        click_blocks.append(block)
        build_entries.append(f'    <p:bldP spid="{sid}" grpId="0"/>')
        ctn_id += 5

    xml = ANIM_CLICK_FADE_TEMPLATE.format(
        click_blocks='\n'.join(click_blocks),
        build_entries='\n'.join(build_entries)
    )
    _inject_timing_xml(slide, xml)


# ============================================================
# 7. 텍스트 위 마스크 리빌 — 마스크는 처음부터 보이고 클릭마다 Fade Out
# ============================================================
CLICK_FADE_OUT_BLOCK = '''                <p:par>
                  <p:cTn id="{base_id}" fill="hold">
                    <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
                    <p:childTnLst>
                      <p:par>
                        <p:cTn id="{id2}" fill="hold">
                          <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                          <p:childTnLst>
                            <p:par>
                              <p:cTn id="{id3}" presetID="10" presetClass="exit" presetSubtype="0"
                                     fill="hold" grpId="0" nodeType="clickEffect">
                                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                                <p:childTnLst>
                                  <p:animEffect transition="out" filter="fade">
                                    <p:cBhvr>
                                      <p:cTn id="{id4}" dur="500" fill="hold"/>
                                      <p:tgtEl><p:spTgt spid="{shape_id}"/></p:tgtEl>
                                    </p:cBhvr>
                                  </p:animEffect>
                                </p:childTnLst>
                              </p:cTn>
                            </p:par>
                          </p:childTnLst>
                        </p:cTn>
                      </p:par>
                    </p:childTnLst>
                  </p:cTn>
                </p:par>'''

ANIM_CLICK_FADE_OUT_TEMPLATE = '''<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:tnLst>
    <p:par>
      <p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">
        <p:childTnLst>
          <p:seq concurrent="1" nextAc="seek">
            <p:cTn id="2" dur="indefinite" nodeType="mainSeq">
              <p:childTnLst>
{click_blocks}
              </p:childTnLst>
            </p:cTn>
            <p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
            <p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
          </p:seq>
        </p:childTnLst>
      </p:cTn>
    </p:par>
  </p:tnLst>
  <p:bldLst>
{build_entries}
  </p:bldLst>
</p:timing>'''


def inject_text_mask_reveal(slide, shape_ids):
    """텍스트 위 마스크를 클릭마다 순차 Fade Out"""
    if not shape_ids:
        return

    click_blocks = []
    build_entries = []
    ctn_id = 3

    for sid in shape_ids:
        block = CLICK_FADE_OUT_BLOCK.format(
            base_id=ctn_id, id2=ctn_id + 1, id3=ctn_id + 2, id4=ctn_id + 3,
            shape_id=sid
        )
        click_blocks.append(block)
        build_entries.append(f'    <p:bldP spid="{sid}" grpId="0"/>')
        ctn_id += 4

    xml = ANIM_CLICK_FADE_OUT_TEMPLATE.format(
        click_blocks='\n'.join(click_blocks),
        build_entries='\n'.join(build_entries)
    )
    _inject_timing_xml(slide, xml)
