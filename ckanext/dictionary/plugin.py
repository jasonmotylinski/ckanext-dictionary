"""Interface into CKAN for the dictionary plugin."""
import ckan.plugins as p
import logging 

from ckanext.dictionary import action

log = logging.getLogger(__name__)

class Data_DictionaryPlugin(p.SingletonPlugin):
    """data dictionary plugin."""

    p.implements(p.IRoutes, inherit=True)
    p.implements(p.IConfigurer)
    p.implements(p.IAuthFunctions, inherit=True)

    def before_map(self, map):
        """UI and API route registration.""" 
        map.connect('dataset_edit_dictionary',
                    '/dataset/dictionary/edit/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action='edit_dictionary',
                    ckan_icon='edit')

        map.connect('data dict button',
                    '/dataset/dictionary/new_dict/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action="new_data_dictionary")

        map.connect('dataset_dictionary',
                    '/dataset/dictionary/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action='dictionary',
                    ckan_icon='info-sign')

        map.connect('api_dictionary_update', '/api/action/dictionary_update',
                    controller='ckanext.dictionary.controller:ApiController',
                    action='dictionary_update')

        return map

    def update_config(self, config_):
        """Configure for static resources."""
        p.toolkit.add_template_directory(config_, 'templates')
        p.toolkit.add_public_directory(config_, 'public')
        p.toolkit.add_resource('fanstatic', 'dictionary')
    
    def get_auth_functions(self):
        """Authorize registration to update data dictionary."""
        log.info("plugin:get_auth_functions")
        return {
            'update_data_dictionary': action.update_data_dictionary
        }
