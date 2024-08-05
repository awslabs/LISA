from fastapi.testclient import TestClient
from models import app

client = TestClient(app)

def test_creat_app():
    """
    ModelName: str 
    ModelId: str 
    InferenceContainer: Optional[InferenceContainer]
    # todo: see if we can validate ec2 instance types
    InstanceType: str 
    ContainerConfig: Optional[ContainerConfig]
    AutoScalingConfig: Optional[AutoScalingConfig]
    """
    response = client.post('/models', json={'ModelName': 'my_first_model', 'ModelId': 'abc123', 'InstanceType': 'm5.large'})
    assert response.status_code == 200
    assert response.json() == {'ModelName': 'my_first_model', 'Status': 'CREATING'}

    response = client.get('/models')
    assert response.status_code == 200
    assert response.json() == [
        {'ModelName': 'my_first_model'},
        {'ModelName': 'my_second_model'},
    ]

    response = client.get('/models/my_first_model')
    assert response.status_code == 200
    assert response.json() == {'ModelName': 'my_first_model'}

    response = client.delete('/models/my_first_model')
    assert response.status_code == 200
    assert response.json() == {'ModelName': 'my_first_model', 'Status': 'DELETED'}